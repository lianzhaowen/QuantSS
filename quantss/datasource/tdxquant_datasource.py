"""
通达信数据源模块
==================

基于 tqcenter 实现的通达信数据接口封装，提供股票行情、股本、除权除息等数据的获取能力。

核心特性：
- 线程安全：通过 threading.local() 实现线程隔离
- 自动重连：连接断开时自动重新建立
- 格式适配：自动处理代码和日期格式转换
"""

import os
import sys
import threading
import pyarrow as pa
import pyarrow.compute as pc
import polars as pl

from datetime import datetime
from typing import List
from quantss.datasource import BaseDataSource
from quantss.common import DataSourceException
from quantss.utils import retry, get_today_date, logger, normalize_trade_date, normalize_stock_code, normalize_index_code
from quantss.models import CAPITALDAILY_PA_SCHEMA, INDEX_PA_SCHEMA, INDEXDAILY_PA_SCHEMA, STOCK_PA_SCHEMA, STOCKDAILY_PA_SCHEMA, TRADEDATE_PA_SCHEMA, STOCKDIVIDEND_PA_SCHEMA, CapitalDaily, Index, IndexDaily, Stock, StockDaily, TradeDate, StockDividend
from quantss.common import CHINA_SECURITY_MARKET_ESTABLISH_DATE, DividendType, KlinePeriod, StockCodeFormat, TradeDateFormat
from quantss.config import settings

# 通达信相关路径配置
TQ_DIR = settings.tdx.TQ_DIR
PYPLUGINS_DIR = settings.tdx.PYPLUGINS_DIR
SYS_DIR = settings.tdx.SYS_DIR

# 动态添加 pyplugins 路径到系统环境（解决 tqcenter 导入失败问题）
if os.path.exists(PYPLUGINS_DIR) and PYPLUGINS_DIR not in sys.path:
    sys.path.insert(0, PYPLUGINS_DIR)

# 动态添加 sys 路径到系统环境（解决通达信底层依赖缺失问题）
if os.path.exists(SYS_DIR) and SYS_DIR not in sys.path:
    sys.path.insert(0, SYS_DIR)


class TdxQuantDataSource(BaseDataSource):
    """
    通达信数据源实现类。
    
    基于 tqcenter 封装，提供 A 股市场的行情和股本数据获取能力，
    支持多线程安全访问。
    """

    def __init__(self):
        """初始化通达信数据源实例"""
        super().__init__()
        self._local_conn = threading.local()

    def _connect(self):
        """
        建立通达信数据接口连接。
        
        每个线程会拥有独立的 tqcenter 实例，实现线程隔离。
        """
        try:
            from tqcenter import tq  # pyright: ignore[reportMissingImports]
            # 每个子线程拥有独立的 tqcenter 实例
            self._local_conn.tq = tq
            self._local_conn.tq.initialize(__file__)
            
            logger.success(f"[TdxQuant] 线程 {threading.current_thread().name} - 数据接口初始化成功")
        except Exception as e:
            logger.error(f"[TdxQuant] 数据接口初始化失败: {str(e)}")
            raise DataSourceException(f"[TdxQuant] 数据接口初始化失败：{str(e)}")

    def _disconnect(self):
        """断开通达信数据接口连接"""
        if hasattr(self._local_conn, "tq") and self._local_conn.tq is not None:
            try:
                self._local_conn.tq.close()
                self._local_conn.tq = None
                logger.success(f"[TdxQuant] 线程 {threading.current_thread().name} - 数据接口连接关闭成功")
            except Exception as e:
                logger.error(f"[TdxQuant] 数据接口连接关闭失败: {str(e)}")
                raise DataSourceException(f"[TdxQuant] 数据接口连接关闭失败：{str(e)}")

    @property
    def tq(self):
        """
        获取当前线程的 tqcenter 实例。
        
        通过 threading.local() 实现线程隔离，每个线程拥有独立的连接实例，
        确保多线程环境下的线程安全。
        """
        if not hasattr(self._local_conn, "tq") or self._local_conn.tq is None:
            self._connect()
        return self._local_conn.tq

    def _convert_stock_code(self, std_code: str) -> str:
        """
        股票代码标准化适配。
        
        Args:
            std_code: 标准格式股票代码（如 600000.SH）
        
        Returns:
            适配通达信接口的后缀格式代码
        """
        return normalize_stock_code(std_code, StockCodeFormat.SUFFIX)

    def _convert_index_code(self, std_code: str) -> str:
        """
        指数代码标准化适配。
        
        Args:
            std_code: 标准格式指数代码
        
        Returns:
            适配通达信接口的后缀格式代码
        """
        return normalize_index_code(std_code, StockCodeFormat.SUFFIX)

    def _convert_trade_date(self, std_date: str) -> str:
        """
        日期标准化适配。
        
        Args:
            std_date: 标准格式日期（如 2024-01-01）
        
        Returns:
            适配通达信接口的纯数字格式日期（如 20240101）
        """
        return normalize_trade_date(std_date, TradeDateFormat.PURE_NUM)

    def _convert_kline_period(self, period: KlinePeriod) -> str:
        period_mapping = {
            KlinePeriod.MINUTE_1: "1m",  
            KlinePeriod.MINUTE_5: "5m",
            KlinePeriod.MINUTE_15: "15m", 
            KlinePeriod.MINUTE_30: "30m",  
            KlinePeriod.MINUTE_60: "1h",
            KlinePeriod.DAY: "1d",        
            KlinePeriod.WEEK: "1w",      
            KlinePeriod.MONTH: "1mon",   
            KlinePeriod.QUARTER: "1q",   
            KlinePeriod.YEAR: "1y",    
        }
        return period_mapping.get(period, "1d")

    def _convert_divid_type(self, adjust: DividendType) -> str:
        adjust_mapping = {
            DividendType.NONE: "none",
            DividendType.FRONT: "front",  
            DividendType.BACK: "back",  
        }
        return adjust_mapping.get(adjust, "none")

    @retry(times=3, delay=0.5)
    def get_trade_date(self, start_date: str, end_date: str) -> pa.Table:
        # 1. 设置内部固定参数
        market = "SH"  # 固定使用上证市场（依赖上证指数判断交易日）
        count = -1     # count=-1表示返回指定时间范围内的全部交易日

        start_date = start_date or CHINA_SECURITY_MARKET_ESTABLISH_DATE
        end_date = end_date or get_today_date()
        
        # 记录调试日志：标记开始拉取交易日列表
        logger.debug(f"[ TdxQuant ] 开始拉取交易日列表 | 时间：{start_date} - {end_date} 🔍")

        try:
            # 3. 调用底层通达信接口获取交易日数据（返回如 ['20251211', '20251212', ...] 的列表）
            data = self.tq.get_trading_dates(
                market=market,
                start_time=self._convert_trade_date(start_date),
                end_time=self._convert_trade_date(end_date),
                count=count
            )

            # 4. 边界条件防御：若通达信返回空，则构建一个带标准 Schema 的空 PyArrow Table
            if not data:
                logger.debug("[ TdxQuant ] 交易日列表拉取成功 | 数据量：0 条")
                return pa.Table.from_pylist([], schema=TRADEDATE_PA_SCHEMA)

            # 5. 向量化数据清洗：完美解析['20251211', ...]结构，消除 Windows 平台时区依赖
            cleaned_dates = [
                normalize_trade_date(item, TradeDateFormat.DATE_CLASS) 
                for item in data
            ]
            pydict = {TradeDate.TRADE_DATE: cleaned_dates}

            # 6. ⚡ 强类型转换：根据 TRADEDATE_PA_SCHEMA 契约将字典一键转为列式 PyArrow.Table
            arrow_table = pa.Table.from_pydict(pydict, schema=TRADEDATE_PA_SCHEMA).sort_by(TradeDate.TRADE_DATE)

            # 记录成功日志：输出本次拉取的交易日数量
            logger.debug(f"[ TdxQuant ] 交易日列表拉取成功 | 数据量：{arrow_table.num_rows} 条")
            return arrow_table

        except Exception as e:
            # 记录错误日志并抛出专用异常
            logger.error(f"[ TdxQuant ] 交易日列表拉取失败 {str(e)}")
            raise DataSourceException(f"[ TdxQuant ] 交易日列表拉取失败 {str(e)}")

    @retry(times=3, delay=0.5)
    def get_stock_list(self) -> pa.Table:
        # 1. 设置内部固定参数
        market = "5"       # market="5"：指定获取所有A股
        # list_type = 0 只返回代码，list_type = 1 返回代码和名称
        list_type = 1

        # 记录调试日志：开始拉取
        logger.debug(f"[ TdxQuant ] 开始拉取股票列表... | 🔍")

        try:
            data = self.tq.get_stock_list(market=market, list_type=list_type)

            if not data:
                logger.debug(f"[ TdxQuant ] 股票列表拉取成功 | 数据量：0 条")
                return pa.Table.from_pylist([], schema=STOCK_PA_SCHEMA)

            codes, names = zip(*(
                (
                    normalize_stock_code(item["Code"], StockCodeFormat.PURE_CODE),
                    item["Name"].strip()
                )
                for item in data
            ))

            final_pydict = {
                Stock.CODE: pa.array(codes, type=pa.string()),
                Stock.NAME: pa.array(names, type=pa.string())
            }

            # 5. ⚡ 强类型零拷贝转换：直接映射为 PyArrow.Table
            arrow_table = pa.Table.from_pydict(final_pydict, schema=STOCK_PA_SCHEMA)

            # 记录成功日志
            logger.debug(f"[ TdxQuant ] 股票列表拉取成功 | 数据量：{len(data) if data else 0} 条")
            return arrow_table
        
        except Exception as e:
            # 记录错误日志并抛出异常
            logger.error(f"[ TdxQuant ] 股票列表拉取失败: {str(e)}")
            raise DataSourceException(f"[ TdxQuant ] 股票列表拉取失败: {str(e)}")

    @retry(times=3, delay=0.5)
    def get_index_list(self) -> pa.Table:
        # 1. 设置内部固定参数
        market = "9"       # market="5"：指定获取所有A股
        # list_type = 0 只返回代码，list_type = 1 返回代码和名称
        list_type = 1

        # 记录调试日志：开始拉取
        logger.debug(f"[ TdxQuant ] 开始拉取指数列表... | 🔍")

        try:
            data = self.tq.get_stock_list(market=market, list_type=list_type)

            if not data:
                logger.debug(f"[ TdxQuant ] 指数列表拉取成功 | 数据量：0 条")
                return pa.Table.from_pylist([], schema=INDEX_PA_SCHEMA)

            codes, names = zip(*(
                (
                    normalize_index_code(item["Code"], StockCodeFormat.PURE_CODE),
                    item["Name"].strip()
                )
                for item in data
            ))

            # 组装最终字典，规避 .append 动态查找，直接交付 PyArrow
            final_pydict = {
                Index.CODE: pa.array(codes, type=pa.string()),
                Index.NAME: pa.array(names, type=pa.string())
            }

            # 5. ⚡ 强类型零拷贝转换：直接映射为 PyArrow.Table
            arrow_table = pa.Table.from_pydict(final_pydict, schema=INDEX_PA_SCHEMA)

            # 记录成功日志
            logger.debug(f"[ TdxQuant ] 指数列表拉取成功 | 数据量：{len(data) if data else 0} 条")
            return arrow_table
        
        except Exception as e:
            # 记录错误日志并抛出异常
            logger.error(f"[ TdxQuant ] 指数列表拉取失败: {str(e)}")
            raise DataSourceException(f"[ TdxQuant ] 指数列表拉取失败: {str(e)}")

    @retry(times=3, delay=1)
    def get_stock_daily(self, code: str, start_date: str, end_date: str) -> pa.Table:
        # 1. 设置内部固定参数
        period = KlinePeriod.DAY  
        dividend_type = DividendType.NONE  

        field_list = ["Open", "High", "Low", "Close", "Volume", "Amount", "ForwardFactor"]
        count = -1
        fill_data = True
        start_date = start_date or CHINA_SECURITY_MARKET_ESTABLISH_DATE
        end_date = end_date or get_today_date()

        logger.debug(
            f"[ TdxQuant ] 开始拉取股票 {code} K线数据... | {start_date} ~ {end_date}"
            f" | 周期：{period} | 复权：{dividend_type} 🔍"
        )

        try:
            # 调用底层通达信接口获取原始行情字典
            data = self.tq.get_market_data(
                stock_list=[self._convert_stock_code(code)],
                field_list=field_list,
                start_time=self._convert_trade_date(start_date),
                end_time=self._convert_trade_date(end_date),
                count=count,
                dividend_type=self._convert_divid_type(dividend_type),
                period=self._convert_kline_period(period),
                fill_data=fill_data
            )

            if not data:
                logger.warning(f"股票 {code} 未查询到日线数据")
                return pa.Table.from_pylist([], schema=STOCKDAILY_PA_SCHEMA)

            # ----------------------------------------------------
            # 🚀 极速列名识别（不遍历所有字段类型，直接基于列名提取）
            # ----------------------------------------------------
            pydict_raw = {}
            date_array = None

            for field_name, df_pd in data.items():
                if df_pd is None or df_pd.empty:
                    continue
                
                # 单列 DataFrame 转化为 Arrow Table
                field_table = pa.Table.from_pandas(df_pd, preserve_index=True)
                names = field_table.schema.names
                
                # 🎯 嗅探定位：一行代码快速分离日期列与数据列
                current_date_col = next((n for n in names if "date" in n.lower() or "index" in n.lower()), names[0])
                current_data_col = next((n for n in names if n != current_date_col), None)

                if not current_data_col:
                    continue

                if date_array is None:
                    date_array = field_table.column(current_date_col)
                
                pydict_raw[field_name] = field_table.column(current_data_col)

            if not pydict_raw or date_array is None:
                logger.warning(f"股票 {code} 解析后无有效数据")
                return pa.Table.from_pylist([], schema=STOCKDAILY_PA_SCHEMA)

            # 2. 缺失字段强健兜底
            total_len = date_array.length()
            for f in ["Open", "High", "Low", "Close"]:
                if f not in pydict_raw:
                    fallback = [col for col in ["Close", "Open", "High", "Low"] if col in pydict_raw]
                    pydict_raw[f] = pydict_raw[fallback[0]] if fallback else pa.array([0.0] * total_len, type=pa.float64())
                        
            for f in ["Volume", "Amount"]:
                if f not in pydict_raw:
                    pydict_raw[f] = pa.array([0.0] * total_len, type=pa.float64())

            # 3. 拼装基础未过滤 Table
            combined_table = pa.Table.from_pydict({"Date": date_array, **pydict_raw})

            # 4. 过滤无效交易日（在 C++ 内存层面直接过滤）
            valid_mask = pc.and_(
                pc.greater(combined_table.column("Close"), 0.0),
                pc.is_valid(combined_table.column("Close"))
            )
            filtered_table = combined_table.filter(valid_mask)

            rows_count = filtered_table.num_rows
            if rows_count == 0:
                logger.warning(f"股票 {code} 过滤无效交易日后无有效数据")
                return pa.Table.from_pylist([], schema=STOCKDAILY_PA_SCHEMA)

            # ----------------------------------------------------
            # 🚀 高性能字典映射区（完全丢弃 Python 循环，100% 内存无损转换）
            # ----------------------------------------------------
            normalized_code = normalize_stock_code(code, StockCodeFormat.PURE_CODE)
            
            # 从最终 Schema 中动态嗅探数据库期望的日期数据类型（如 pa.date32()、pa.string() 等）
            target_date_type = STOCKDAILY_PA_SCHEMA.field(StockDaily.TRADE_DATE).type
            code_field_type = INDEXDAILY_PA_SCHEMA.field(StockDaily.CODE).type

            final_pydict = {
                StockDaily.CODE: pa.array([normalized_code] * rows_count, type=code_field_type),
                StockDaily.TRADE_DATE: pc.cast(filtered_table.column("Date"), target_date_type),
                StockDaily.OPEN: filtered_table.column("Open"),
                StockDaily.HIGH: filtered_table.column("High"),
                StockDaily.LOW: filtered_table.column("Low"),
                StockDaily.CLOSE: filtered_table.column("Close"),
                StockDaily.VOLUME: filtered_table.column("Volume"),
                StockDaily.AMOUNT: filtered_table.column("Amount")
            }

            # 5. 强类型对齐转换并排序
            result_table = pa.Table.from_pydict(final_pydict, schema=STOCKDAILY_PA_SCHEMA).sort_by(StockDaily.TRADE_DATE)

            logger.debug(f"[ TdxQuant ] 股票 {code} 日线拉取成功 | {result_table.num_rows} 条")
            return result_table

        except Exception as e:
            logger.error(f"[ TdxQuant ] 股票 {code} 拉取失败: {str(e)}")
            raise DataSourceException(f"股票 {code} 拉取失败: {str(e)}")

    @retry(times=3, delay=0.5)
    def get_index_daily(self, code: str, start_date: str, end_date: str) -> pa.Table:
        # 🎯 修复函数签名返回值声明：从 List[IndexDaily] 修改为符合实际的 pa.Table
        period = KlinePeriod.DAY  
        dividend_type = DividendType.NONE  

        field_list = ["Open", "High", "Low", "Close", "Volume", "Amount", "ForwardFactor"]
        count = -1
        fill_data = True
        start_date = start_date or CHINA_SECURITY_MARKET_ESTABLISH_DATE
        end_date = end_date or get_today_date()

        logger.debug(
            f"[ TdxQuant ] 开始拉取指数 {code} K线数据... | {start_date} ~ {end_date}"
            f" | 周期：{period} | 复权：{dividend_type} 🔍"
        )

        try:
            # 调用底层通达信接口获取原始行情字典（注意此处已使用 _convert_index_code）
            data = self.tq.get_market_data(
                stock_list=[self._convert_index_code(code)],
                field_list=field_list,
                start_time=self._convert_trade_date(start_date),
                end_time=self._convert_trade_date(end_date),
                count=count,
                dividend_type=self._convert_divid_type(dividend_type),
                period=self._convert_kline_period(period),
                fill_data=fill_data
            )

            if not data:
                logger.warning(f"指数 {code} 未查询到日线数据")
                return pa.Table.from_pylist([], schema=INDEXDAILY_PA_SCHEMA)

            pydict_raw = {}
            date_array = None

            for field_name, df_pd in data.items():
                if df_pd is None or df_pd.empty:
                    continue
                
                field_table = pa.Table.from_pandas(df_pd, preserve_index=True)
                names = field_table.schema.names
                
                current_date_col = next((n for n in names if "date" in n.lower() or "index" in n.lower()), names[0])
                current_data_col = next((n for n in names if n != current_date_col), None)

                if not current_data_col:
                    continue

                if date_array is None:
                    date_array = field_table.column(current_date_col)
                
                pydict_raw[field_name] = field_table.column(current_data_col)

            if not pydict_raw or date_array is None:
                logger.warning(f"指数 {code} 解析后无有效数据")
                return pa.Table.from_pylist([], schema=INDEXDAILY_PA_SCHEMA)

            total_len = date_array.length()
            for f in ["Open", "High", "Low", "Close"]:
                if f not in pydict_raw:
                    # 💡 Bug 修复：提取第一个命中字段的 Arrow 独立列，而不是直接透传整个 fallback 列表
                    fallback = [col for col in ["Close", "Open", "High", "Low"] if col in pydict_raw]
                    pydict_raw[f] = pydict_raw[fallback[0]] if fallback else pa.array([0.0] * total_len, type=pa.float64())
                        
            for f in ["Volume", "Amount"]:
                if f not in pydict_raw:
                    pydict_raw[f] = pa.array([0.0] * total_len, type=pa.float64())

            combined_table = pa.Table.from_pydict({"Date": date_array, **pydict_raw})

            valid_mask = pc.and_(
                pc.greater(combined_table.column("Close"), 0.0),
                pc.is_valid(combined_table.column("Close"))
            )
            filtered_table = combined_table.filter(valid_mask)

            rows_count = filtered_table.num_rows
            if rows_count == 0:
                logger.warning(f"指数 {code} 过滤无效交易日后无有效数据")
                return pa.Table.from_pylist([], schema=INDEXDAILY_PA_SCHEMA)

            normalized_code = normalize_index_code(code, StockCodeFormat.PURE_CODE)
            
            target_date_type = INDEXDAILY_PA_SCHEMA.field(IndexDaily.TRADE_DATE).type
            code_field_type = INDEXDAILY_PA_SCHEMA.field(IndexDaily.CODE).type

            final_pydict = {
                IndexDaily.CODE: pa.array([normalized_code] * rows_count, type=code_field_type),
                IndexDaily.TRADE_DATE: pc.cast(filtered_table.column("Date"), target_date_type), # ⚡ C++ 级别清洗
                IndexDaily.OPEN: filtered_table.column("Open"),
                IndexDaily.HIGH: filtered_table.column("High"),
                IndexDaily.LOW: filtered_table.column("Low"),
                IndexDaily.CLOSE: filtered_table.column("Close"),
                IndexDaily.VOLUME: filtered_table.column("Volume"),
                IndexDaily.AMOUNT: filtered_table.column("Amount")
            }

            result_table = pa.Table.from_pydict(final_pydict, schema=INDEXDAILY_PA_SCHEMA).sort_by(IndexDaily.TRADE_DATE)

            logger.debug(f"[ TdxQuant ] 指数 {code} 日线拉取成功 | {result_table.num_rows} 条")
            return result_table

        except Exception as e:
            logger.error(f"[ TdxQuant ] 指数 {code} 拉取失败: {str(e)}")
            raise DataSourceException(f"指数 {code} 拉取失败: {str(e)}") 

    @retry(times=3, delay=0.5)
    def get_divid_factor(self, code: str, start_date: str, end_date: str) -> pa.Table:
        # 记录调试日志：标记开始拉取分红配送数据
        logger.debug(f"[ TdxQuant ] 开始拉取 {code} 分红配送数据... | 时间：{start_date} - {end_date} 🔍")

        try:
            start_date = start_date or CHINA_SECURITY_MARKET_ESTABLISH_DATE
            end_date = end_date or get_today_date()

            # 2. 调用底层通达信接口获取分红配送数据
            data = self.tq.get_divid_factors(
                stock_code=self._convert_stock_code(code),
                start_time=self._convert_trade_date(start_date),
                end_time=self._convert_trade_date(end_date)
            )

            # 3. 边界条件防御：统一改用当前服务的 XDXR_PA_SCHEMA 返回空表
            if data is None or data.empty:
                logger.debug(f"[ TdxQuant ] {code} 分红配送数据拉取成功 | 数据量：0 条")
                return pa.Table.from_pylist([], schema=STOCKDIVIDEND_PA_SCHEMA)

            # 4. ⚡ 瞬间穿透：直接将原始 Pandas 转化为独立的 Arrow Table，并保留 Date 索引为普通列
            raw_table = pa.Table.from_pandas(data, preserve_index=True)

            # 5. 精确获取日期列：兼容通达信返回的索引名 "Date" 或 reset 后的普通列
            date_col_name = next((n for n in raw_table.schema.names if "date" in n.lower() or "index" in n.lower()), "Date")
            
            rows_count = raw_table.num_rows
            normalized_code = normalize_stock_code(code, StockCodeFormat.PURE_CODE)

            # ----------------------------------------------------
            # 🚀 高性能字典映射区（从 XDXR_PA_SCHEMA 动态卡位，100% 去 Python 循环）
            # ----------------------------------------------------
            # 🎯 从模型中提取具体的强类型，使得 pc.cast 完全由 Schema 驱动
            code_field_type = STOCKDIVIDEND_PA_SCHEMA.field(StockDividend.CODE).type
            target_date_type = STOCKDIVIDEND_PA_SCHEMA.field(StockDividend.TRADE_DATE).type
            category_type = STOCKDIVIDEND_PA_SCHEMA.field(StockDividend.CATEGORY).type
            dividend_type = STOCKDIVIDEND_PA_SCHEMA.field(StockDividend.DIVIDEND).type
            bonus_ratio_type = STOCKDIVIDEND_PA_SCHEMA.field(StockDividend.BONUS_RATIO).type
            rights_ratio_type = STOCKDIVIDEND_PA_SCHEMA.field(StockDividend.RIGHTS_RATIO).type
            rights_price_type = STOCKDIVIDEND_PA_SCHEMA.field(StockDividend.RIGHTS_PRICE).type

            final_pydict = {
                StockDividend.CODE: pa.array([normalized_code] * rows_count, type=code_field_type),
                StockDividend.TRADE_DATE: pc.cast(raw_table.column(date_col_name), target_date_type), # ⚡ C++ 级别清洗日期
                StockDividend.CATEGORY: pc.cast(raw_table.column("Type"), category_type),
                StockDividend.DIVIDEND: pc.cast(raw_table.column("Bonus"), dividend_type),
                StockDividend.BONUS_RATIO: pc.cast(raw_table.column("ShareBonus"), bonus_ratio_type),
                StockDividend.RIGHTS_RATIO: pc.cast(raw_table.column("Allotment"), rights_ratio_type),
                StockDividend.RIGHTS_PRICE: pc.cast(raw_table.column("AllotPrice"), rights_price_type)
            }

            # 5. 强类型对齐转换并按照除权除息日排序
            # 💡 优化：移除末尾冗余的 .cast(STOCKDIVIDEND_PA_SCHEMA)，因为 from_pydict 传入 schema 时已经原地完成了类型固化
            result_table = pa.Table.from_pydict(final_pydict, schema=STOCKDIVIDEND_PA_SCHEMA).sort_by(StockDividend.TRADE_DATE)

            # 记录成功日志：输出本次拉取的分红配送数据量
            logger.debug(f"[ TdxQuant ] {code} 分红配送数据拉取成功 | 数据量：{result_table.num_rows} 条")
            return result_table

        except Exception as e:
            # 记录错误日志并抛出专用异常
            logger.error(f"[ TdxQuant ] {code} 分红配送数据拉取失败: {str(e)}")
            raise DataSourceException(f"[ TdxQuant ] {code} 分红配送数据拉取失败: {str(e)}")

    @retry(times=3, delay=0.5)
    def get_capital_daily(self, code: str, start_date: str, end_date: str) -> pa.Table:
        start_date = start_date or CHINA_SECURITY_MARKET_ESTABLISH_DATE
        end_date = end_date or get_today_date()

        trade_dates_table = self.get_trade_date(start_date, end_date)
        if trade_dates_table.num_rows == 0:
            logger.debug(f"[ TdxQuant ] {code} 股票股本数据拉取成功 | 数据量：0 条")
            return pa.Table.from_pylist([], schema=CAPITALDAILY_PA_SCHEMA)
        
        date_list = [normalize_trade_date(date, TradeDateFormat.PURE_NUM) for date in trade_dates_table.column(TradeDate.TRADE_DATE).to_pylist()]
        count = len(date_list)

        try:
            # 3. 调用底层通达信接口获取股本数据
            data = self.tq.get_gb_info(
                stock_code=self._convert_stock_code(code),
                date_list=date_list,
                count=count
            )

            # 4. 边界条件防御
            if not data:
                logger.debug(f"[ TdxQuant ] {code} 股票股本数据拉取成功 | 数据量：0 条")
                return pa.Table.from_pylist([], schema=CAPITALDAILY_PA_SCHEMA)

            # ----------------------------------------------------
            # 🚀 矩阵转置：利用 zip(*...) 将行式 List[dict] 瞬间拉平为列
            # ----------------------------------------------------
            raw_dates, zgb_list, ltgb_list = zip(*(
                (str(item["Date"]), item["Zgb"], item["Ltgb"])
                for item in data
            ))

            rows_count = len(data)
            normalized_code = normalize_stock_code(code, StockCodeFormat.PURE_CODE)

            # ----------------------------------------------------
            # 🚀 Schema 类型卡位与强健时序穿透
            # ----------------------------------------------------
            code_field_type = CAPITALDAILY_PA_SCHEMA.field(CapitalDaily.CODE).type
            target_date_type = CAPITALDAILY_PA_SCHEMA.field(CapitalDaily.TRADE_DATE).type
            total_share_type = CAPITALDAILY_PA_SCHEMA.field(CapitalDaily.TOTAL_SHARE).type
            float_share_type = CAPITALDAILY_PA_SCHEMA.field(CapitalDaily.FLOAT_SHARE).type

            # 🎯 核心修正：利用 pc.strptime 兼容通达信 "YYYYMMDD" 的文本日期
            # 先用 C++ 引擎按指定格式转为 timestamp，再原位强转为目标 Schema 日期类型
            arrow_raw_dates = pa.array(raw_dates, type=pa.string())
            parsed_timestamps = pc.strptime(arrow_raw_dates, format="%Y%m%d", unit="s")
            cleaned_dates = pc.cast(parsed_timestamps, target_date_type)

            final_pydict = {
                CapitalDaily.CODE: pa.array([normalized_code] * rows_count, type=code_field_type),
                CapitalDaily.TRADE_DATE: cleaned_dates,
                CapitalDaily.TOTAL_SHARE: pa.array(zgb_list, type=total_share_type),
                CapitalDaily.FLOAT_SHARE: pa.array(ltgb_list, type=float_share_type)
            }

            # 5. 一体化强类型收网与排序
            result_table = pa.Table.from_pydict(final_pydict, schema=CAPITALDAILY_PA_SCHEMA).sort_by(CapitalDaily.TRADE_DATE)

            logger.debug(f"[ TdxQuant ] {code} 股票股本数据拉取成功 | 数据量：{result_table.num_rows} 条")
            return result_table

        except Exception as e:
            logger.error(f"[ TdxQuant ] {code} 股票股本数据拉取失败: {str(e)}")
            raise DataSourceException(f"[ TdxQuant ] {code} 股票股本数据拉取失败: {str(e)}")

if __name__ == "__main__":
    """测试入口：验证各数据接口功能"""
    print("TdxQuantDataSource test")

    datasource = TdxQuantDataSource()

    try:
        datasource.connect()

        # stock_list = [item["Code"] for item in datasource.tq.get_stock_list("5", 1)]
        # df = datasource.tq.get_gpjy_value(["600519.SH"], field_list=["GP21"], start_time="20260401", end_time="20260507")
        # print(df)

        # # 测试交易日获取
        trade_date = datasource.get_trade_date("20240101", "2024-12-31")
        print("交易日列表（最后5条）：", trade_date[-5:])

        # 测试股票列表获取
        stock_list = datasource.get_stock_list()
        print("股票列表（最后5条）：", stock_list[-5:])

        index_list = datasource.get_index_list()
        print("指数列表（最后5条）：", index_list[-5:])

        # # 测试日线数据获取
        stock_day = datasource.get_stock_daily("302132", "20240101", "20241231")
        print("股票日线数据（最后5条）：", stock_day[-5:])

        index_day = datasource.get_index_daily("880082", "20240101", "20241231")
        print("指数日线数据（最后5条）：", index_day[-5:])

        # 测试分红配送数据获取
        divid_factor = datasource.get_divid_factor("000001", "20240101", "20241231")
        print("分红配送数据（最后5条）：", divid_factor[-5:])

        # # 测试股本数据获取
        stock_capital = datasource.get_capital_daily("000001", "2021-01-01", "2021-01-03")
        print("股本数据（最后5条）：", stock_capital[-5:])

    except Exception as e:
        print(f"获取数据失败 {str(e)}")