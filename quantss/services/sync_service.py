import threading
import queue
import time
import datetime
import pyarrow as pa
from tqdm import tqdm

from typing import Dict, Optional, Any, Type
from abc import ABC, abstractmethod
from quantss.common import CHINA_SECURITY_MARKET_ESTABLISH_DATE, TradeDateFormat, StockCodeFormat
from quantss.common.enums import InsertMode
from quantss.config import settings
from quantss.database import T
from quantss.manager import database, datasource
from quantss.models import Index, IndexDaily, Stock, StockDaily, CapitalDaily, TradeDate, StockDividend
from quantss.utils.logger import logger
from quantss.utils.standardize import get_today_date, normalize_trade_date, normalize_stock_code

class BaseSyncService(ABC):
    """
    同步服务基类，提供通用的全量同步和增量同步能力。
    
    配置常量：
        BATCH_WRITE_SIZE: 批量写入阈值
        QUEUE_MAX_SIZE: 写入队列最大容量
        SERVICE_NAME: 服务名称标识
        MODEL: 数据模型类
    
    progress_map 格式: {code: {"start_date": str, "end_date": str}}
    """

    BATCH_WRITE_SIZE = settings.app.BATCH_WRITE_SIZE
    QUEUE_MAX_SIZE = settings.app.QUEUE_MAX_SIZE
    MAX_FLUSH_STOCKS = settings.app.MAX_FLUSH_STOCKS
    SERVICE_NAME = "BaseSync"
    MODEL: Type[T] = None

    _write_lock = threading.Lock()

    @classmethod
    def _get_max_trade_date(cls) -> str:
        """
        获取 TradeDate 表中的最新交易日
        
        Returns:
            最新交易日字符串 "YYYYMMDD"（纯数字格式）
        """
        latest_trade_date_df = database.aggregate(
            model_cls=TradeDate,
            agg_exprs={"result": f"MAX({TradeDate.TRADE_DATE})"}
        )
        if latest_trade_date_df is None or latest_trade_date_df.num_rows == 0:
            logger.warning(f"[ {cls.SERVICE_NAME} ] 无法获取最新交易日，使用今日日期替代")
            return normalize_trade_date(get_today_date(), TradeDateFormat.PURE_NUM)
        latest_date = latest_trade_date_df["result"][0].as_py()
        return normalize_trade_date(latest_date, TradeDateFormat.PURE_NUM)

    @classmethod
    def sync_all(cls, start_date: Optional[str] = None, end_date: Optional[str] = None, callback: Optional[Any] = None) -> None:
        """
        执行全量同步，覆盖指定日期范围内的所有数据。
        
        Args:
            start_date: 起始日期，默认为中国证券市场建立日期
            end_date: 结束日期，默认为 TradeDate 表中的最新交易日
            callback: 进度回调函数，接收 current, total, code 参数
        """
        max_trade_date = cls._get_max_trade_date()
        end_date = end_date or max_trade_date
        start_date = start_date or CHINA_SECURITY_MARKET_ESTABLISH_DATE
        
        # 构建全量同步的 progress_map
        entity_list = cls.get_entity_list()
        progress_map = {}
        for code in entity_list.column("code").to_pylist():
            progress_map[code] = {"start_date": start_date, "end_date": end_date}
        
        logger.debug(f"[ {cls.SERVICE_NAME} ] 启动全量同步 | {start_date} ~ {end_date} | 共 {len(progress_map)} 只股票")
        cls._execute_sync(progress_map=progress_map, write_mode=InsertMode.REPLACE, callback=callback)

    @classmethod
    def sync_incremental(cls, end_date: Optional[str] = None, callback: Optional[Any] = None) -> None:
        """
        执行增量同步，仅同步未同步的数据。
        
        Args:
            end_date: 结束日期，默认为 TradeDate 表中的最新交易日
            callback: 进度回调函数，接收 current, total, code 参数
        """
        max_trade_date = cls._get_max_trade_date()
        end_date = normalize_trade_date(end_date or max_trade_date, TradeDateFormat.PURE_NUM)
        
        # 获取数据库中已同步的进度
        progress_df = database.aggregate_groupby(
            model_cls=cls.MODEL,
            groupby_cols=[cls.MODEL.CODE],
            agg_exprs={"last_sync_date": f"MAX({cls.MODEL.TRADE_DATE})"}
        )
        
        # 构建增量同步的 progress_map
        # 只包含 last_sync_date != max_trade_date 的股票
        entity_list = cls.get_entity_list()
        entity_codes = set(entity_list.column("code").to_pylist())
        
        # 一次遍历完成：同时记录已存在代码和需要增量同步的股票
        db_existing_codes = set()
        progress_map = {}
        for item in progress_df.to_pylist():
            code = item[cls.MODEL.CODE]
            db_existing_codes.add(code)
            if code not in entity_codes:
                continue
            last_sync = item["last_sync_date"]
            # 使用 normalize_trade_date 统一格式进行比较
            last_sync_normalized = normalize_trade_date(last_sync, TradeDateFormat.PURE_NUM)
            if last_sync_normalized != max_trade_date:
                progress_map[code] = {"start_date": last_sync, "end_date": end_date}
        
        # 首次同步的股票：entity_codes 中不在数据库中的
        for code in entity_codes - db_existing_codes:
            progress_map[code] = {"start_date": CHINA_SECURITY_MARKET_ESTABLISH_DATE, "end_date": end_date}
        
    
        logger.debug(f"[ {cls.SERVICE_NAME} ] 启动增量同步 | 需要同步: {len(progress_map)} 只股票")
        cls._execute_sync(progress_map=progress_map, write_mode=InsertMode.IGNORE, callback=callback)

    @classmethod
    def _execute_sync(
        cls,
        progress_map: Dict[str, dict],
        write_mode: InsertMode,
        callback: Optional[Any] = None,
    ) -> None:
        """
        执行同步操作的核心方法。
        
        采用生产者-消费者模式：
        - 主线程：单线程拉取数据，避免并发 Socket 冲突
        - 后台线程：异步写入数据库，释放主线程压力
        
        Args:
            progress_map: 同步进度映射表 {code: {"start_date": str, "end_date": str}}
            write_mode: 写入模式（REPLACE/IGNORE）
            callback: 进度回调函数
        """
        total_stocks = len(progress_map)
        logger.debug(f"[ {cls.SERVICE_NAME} ] 需要同步的股票数：{total_stocks}")

        if total_stocks == 0:
            logger.info(f"[ {cls.SERVICE_NAME} ] 没有需要同步的股票")
            return

        # 初始化后台写入队列和停止信号
        data_queue = queue.Queue(maxsize=cls.QUEUE_MAX_SIZE)
        stop_event = threading.Event()

        # 启动写入消费者线程
        write_thread = threading.Thread(
            target=cls._write_consumer,
            args=(data_queue, stop_event, write_mode),
            daemon=True
        )
        write_thread.start()

        # 单线程拉取流程，规避并发 Socket 锁冲突
        logger.debug(f"[ {cls.SERVICE_NAME} ] 启动单线程拉取")
        
        pbar = tqdm(
            progress_map.items(),
            desc=f"[ {cls.SERVICE_NAME} ] 拉取进度",
            unit="只",
            colour="green",
            total=total_stocks
        )

        for i, (code, date_range) in enumerate(pbar, 1):
            # 检测停止信号
            if stop_event.is_set():
                break

            try:
                pbar.set_postfix({"当前股票": code}, refresh=True)

                start_date = date_range["start_date"]
                end_date = date_range["end_date"]

                # 统一日期格式进行比较
                start_date_normalized = normalize_trade_date(start_date, TradeDateFormat.PURE_NUM)
                end_date_normalized = normalize_trade_date(end_date, TradeDateFormat.PURE_NUM)

                # 仅同步时间范围内的数据
                if start_date_normalized <= end_date_normalized:
                    logger.debug(f"[ {code} ] 拉取数据: {start_date_normalized} ~ {end_date_normalized}")
                    data = cls.fetch_data(
                        datasource,
                        normalize_stock_code(code, StockCodeFormat.SUFFIX),
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if data is not None and data.num_rows > 0:
                        logger.debug(f"[ {code} ] 获取到 {data.num_rows} 条数据，加入队列")
                        # ⚡ 优化：背压流量控制 - 带重试的队列写入
                        cls._safe_put_with_backpressure(data_queue, data, code)
                    else:
                        logger.debug(f"[ {code} ] 未获取到数据或数据为空")

                # 调用回调函数，传入当前进度
                if callback:
                    callback(current=i, total=total_stocks, code=code)

            except Exception as e:
                logger.error(f"[ {code} ] 拉取失败：{str(e)}")

        # 结束流程：停止消费者线程并等待写入完成
        pbar.close()
        stop_event.set()
        write_thread.join()
        logger.debug(f"[ {cls.SERVICE_NAME} ] 同步完成")

    @classmethod
    def _safe_put_with_backpressure(cls, data_queue: queue.Queue, data: pa.Table, code: str) -> None:
        """
        带背压控制的安全队列写入方法。
        
        当队列满时，采用指数退避策略进行重试，避免数据丢失。
        
        Args:
            data_queue: 目标队列
            data: 待写入数据
            code: 股票代码（用于日志记录）
        """
        max_retries = 3
        retry_delay = 1.0  # 初始重试延迟（秒）
        
        for attempt in range(max_retries):
            try:
                data_queue.put(data, timeout=5.0)
                return
            except queue.Full:
                if attempt == max_retries - 1:
                    logger.error(f"[ {code} ] 队列持续满，丢弃 {data.num_rows} 条数据")
                    return
                wait_time = retry_delay * (2 ** attempt)  # 指数退避
                logger.warning(f"[ {code} ] 队列满，{wait_time:.1f}s 后重试 ({attempt+1}/{max_retries})")
                time.sleep(wait_time)

    @classmethod
    def _write_consumer(cls, data_queue: queue.Queue, stop_event: threading.Event, write_mode: InsertMode) -> None:
        """
        写入消费者线程，负责从队列中获取数据并批量写入数据库。
        
        工作机制：
        1. 从队列中获取数据，累积到内存缓冲区
        2. 当缓冲区达到 BATCH_WRITE_SIZE 或超过 WRITE_TIMEOUT 秒时，批量写入数据库
        3. 单只股票数据量较大时直接写入，不等待
        4. 支持两种写入模式：REPLACE（覆盖）和 IGNORE（防重追加）
        
        Args:
            data_queue: 数据队列
            stop_event: 停止信号
            write_mode: 写入模式
        """
        total_inserted = 0
        buffer = []
        current_rows = 0
        last_write_time = time.time()
        WRITE_TIMEOUT = 5.0  # 超时时间

        def _execute_batch_insert(table: pa.Table) -> int:
            """内部方法：执行批量插入（带超时保护）"""
            nonlocal last_write_time
            import threading
            
            result = [None]
            exception = [None]
            
            def insert_task():
                try:
                    if write_mode == InsertMode.REPLACE:
                        res = database.batch_insert(cls.MODEL, table, mode=InsertMode.REPLACE)
                    else:
                        res = database.batch_insert_ignore(cls.MODEL, table)
                    result[0] = res
                except Exception as e:
                    exception[0] = e
            
            # 创建并启动写入线程，设置30秒超时
            insert_thread = threading.Thread(target=insert_task, daemon=True)
            insert_thread.start()
            insert_thread.join(timeout=30)
            
            if insert_thread.is_alive():
                logger.error(f"[写入超时] 数据库写入超过30秒，强制跳过")
                last_write_time = time.time()
                return 0
            
            if exception[0]:
                logger.error(f"[写入失败] {exception[0]}")
                last_write_time = time.time()
                return 0
            
            res = result[0]
            last_write_time = time.time()
            inserted = res.get("inserted", 0) if isinstance(res, dict) else (res if isinstance(res, int) else 0)
            return inserted

        def _flush_buffer():
            """刷新缓冲区"""
            nonlocal buffer, current_rows, total_inserted
            
            if not buffer:
                return
            
            try:
                merged_table = pa.concat_tables(buffer)
                res = _execute_batch_insert(merged_table)
                total_inserted += res
                logger.info(f"[流式写入] 合并 {len(buffer)} 只股票，共 {merged_table.num_rows} 条数据 | 累计：{total_inserted}")
            except Exception as e:
                logger.error(f"[缓冲区写入失败] {e}")
            finally:
                buffer = []
                current_rows = 0

        logger.info(f"[写入线程启动] 批量阈值: {cls.BATCH_WRITE_SIZE}, 最大股票数: {cls.MAX_FLUSH_STOCKS}, 超时: {WRITE_TIMEOUT}s")
        
        while True:
            # 停止信号已设置且队列为空时，处理剩余数据并退出
            if stop_event.is_set() and data_queue.empty():
                _flush_buffer()
                logger.info(f"[写入线程退出] 累计写入 {total_inserted} 条数据")
                break

            try:
                # 非阻塞获取数据
                data = data_queue.get(timeout=0.05)
                
                if isinstance(data, pa.Table) and data.num_rows > 0:
                    # 所有数据进入缓冲区，统一批量写入
                    buffer.append(data)
                    current_rows += data.num_rows
                    
                    # 达到批量阈值或累积股票数达到上限立即写入
                    if len(buffer) >= cls.MAX_FLUSH_STOCKS or current_rows >= cls.BATCH_WRITE_SIZE:
                        _flush_buffer()
                data_queue.task_done()
            except queue.Empty:
                pass

    # ===================== 抽象方法（子类必须实现）=====================
    @staticmethod
    @abstractmethod
    def get_entity_list() -> pa.Table:
        """获取待同步的实体列表（股票/指数等）"""
        pass

    @staticmethod
    @abstractmethod
    def fetch_data(ds: Any, code: str, **kwargs) -> pa.Table:
        """
        从数据源获取指定实体的数据。
        
        Args:
            ds: 数据源实例
            code: 实体代码
            **kwargs: 额外参数（如 start_date, end_date）
        
        Returns:
            PyArrow Table 数据
        """
        pass

    # get_sync_progress 已在基类中实现，子类可直接继承使用

# ==========================================================================
# 业务同步服务类（基于抽象基类实现具体业务逻辑）
# ==========================================================================

class CapitalDailySyncService(BaseSyncService):
    SERVICE_NAME = "每日股本同步"
    MODEL = CapitalDaily

    @staticmethod
    def get_entity_list():
        return datasource.get_stock_list()  # 股票列表

    @staticmethod
    def fetch_data(ds: Any, code: str, **kwargs) -> pa.Table:
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        # 获取指定时间范围内的交易日列表
        return ds.get_capital_daily(code=code, start_date=start_date, end_date=end_date)

class StockDailySyncService(BaseSyncService):
    SERVICE_NAME = "股票日线数据同步"
    MODEL = StockDaily

    @staticmethod
    def get_entity_list():
        return datasource.get_stock_list()  # 股票列表

    @staticmethod
    def fetch_data(ds: Any, code: str, **kwargs) -> pa.Table:
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        return ds.get_stock_daily(code=code, start_date=start_date, end_date=end_date)

class IndexDailySyncService(BaseSyncService):
    SERVICE_NAME = "指数日线数据同步"
    MODEL = IndexDaily

    @staticmethod
    def get_entity_list():
        return datasource.get_index_list()  # 指数列表

    @staticmethod
    def fetch_data(ds: Any, code: str, **kwargs) -> pa.Table:
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        return ds.get_index_daily(code=code, start_date=start_date, end_date=end_date)

class StockDividendSyncService(BaseSyncService):
    SERVICE_NAME = "除权除息同步"
    MODEL = StockDividend

    @staticmethod
    def get_entity_list():
        return datasource.get_stock_list()

    @staticmethod
    def fetch_data(ds: Any, code: str, **kwargs) -> pa.Table:
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        return ds.get_divid_factor(code=code, start_date=start_date, end_date=end_date)

class StockSyncService:
    @staticmethod
    def sync_all() -> None:
        data = datasource.get_stock_list()
        result = database.batch_insert_ignore(Stock, data)
        logger.debug(f"[股票基础信息同步] 新增：{result['inserted']} | 忽略：{result['ignored']}")


class IndexSyncService:
    @staticmethod
    def sync_all() -> None:
        data = datasource.get_index_list()
        result = database.batch_insert_ignore(Index, data)
        logger.debug(f"[指数基础信息同步] 新增：{result['inserted']} | 忽略：{result['ignored']}")

class TradeDateSyncService:
    @staticmethod
    def sync_all() -> None:
        start_date = CHINA_SECURITY_MARKET_ESTABLISH_DATE
        end_date = get_today_date()

        data = datasource.get_trade_date(start_date=start_date, end_date=end_date)
        result = database.batch_insert_ignore(TradeDate, data)
        logger.debug(f"[交易日历同步] 新增：{result['inserted']} | 忽略：{result['ignored']}")


if __name__ == "__main__":
    # 测试用例（按需取消注释）

    # CapitalDailySyncService.sync_all()
    # IndexDailySyncService.sync_all()
    # CapitalDailySyncService.sync_incremental()

    # StockDailySyncService.sync_all()
    # StockDailySyncService.sync_incremental()

    # StockDividendSyncService.sync_all()
    # StockDividendSyncService.sync_incremental()

    StockSyncService.sync_all()
    IndexSyncService.sync_all()
    TradeDateSyncService.sync_all()