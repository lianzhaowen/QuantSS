"""
Baostock 数据源模块
===================

基于 baostock 开源库实现的数据接口封装，提供股票行情、基本面等数据的获取能力。

核心特性：
- 免费开源：无需注册即可获取 A 股历史数据
- 数据全面：包含日线、周线、月线行情及基本面数据
- 自动登录：首次连接时自动登录获取授权

注意：
- baostock 接口有访问频率限制，调用间隔建议 >= 1 秒
- 数据更新可能有延迟，不适合高频实时交易场景
- 需要先安装 baostock: pip install baostock
"""

import pyarrow as pa
import pandas as pd
import numpy as np

from datetime import datetime
from typing import List
from quantss.datasource import BaseDataSource
from quantss.common import DataSourceException
from quantss.utils import logger, normalize_trade_date, normalize_stock_code
from quantss.models import STOCK_PA_SCHEMA, STOCKDAILY_PA_SCHEMA, TRADEDATE_PA_SCHEMA, Stock, StockDaily, TradeDate
from quantss.common import DividendType, KlinePeriod, StockCodeFormat, TradeDateFormat


# 延迟导入 baostock，避免未安装时影响其他模块
def _import_baostock():
    """延迟导入 baostock 模块"""
    try:
        import baostock as bs
        return bs
    except ImportError:
        raise DataSourceException(
            "[Baostock] 未安装 baostock 模块，请先安装: pip install baostock"
        )


class BaostockDataSource(BaseDataSource):
    """
    Baostock 数据源实现类。
    
    基于 baostock 库封装，提供 A 股市场的历史和基本面数据获取能力。
    
    Attributes:
        _lg: baostock 登录对象，用于维护会话状态
    """

    def __init__(self):
        """初始化 Baostock 数据源实例"""
        super().__init__()
        self._lg = None
        self._bs = None  # 延迟导入的 baostock 模块引用

    def _connect(self) -> None:
        """
        建立 Baostock 数据接口连接。
        
        调用 baostock.login() 获取授权，初始化数据会话。
        """
        try:
            # 延迟导入 baostock 模块
            self._bs = _import_baostock()
            self._lg = self._bs.login()
            if self._lg.error_code != "0":
                raise DataSourceException(
                    f"[Baostock] 登录失败: {self._lg.error_code} - {self._lg.error_msg}"
                )
            logger.success(f"[Baostock] 数据接口登录成功")
        except Exception as e:
            logger.error(f"[Baostock] 数据接口连接失败: {str(e)}")
            raise DataSourceException(f"[Baostock] 数据接口连接失败: {str(e)}")

    def _disconnect(self) -> None:
        """
        断开 Baostock 数据接口连接。
        
        调用 baostock.logout() 释放会话资源。
        """
        if self._lg is not None:
            try:
                self._bs.logout()
                self._lg = None
                self._bs = None
                logger.success("[Baostock] 数据接口登出成功")
            except Exception as e:
                logger.error(f"[Baostock] 数据接口登出失败: {str(e)}")
                raise DataSourceException(f"[Baostock] 数据接口登出失败: {str(e)}")

    def _ensure_connected(self) -> None:
        """
        确保连接已建立。
        
        如果未连接，自动调用 connect() 建立连接。
        """
        if not self.connected:
            self.connect()

    def _convert_stock_code(self, std_code: str) -> str:
        """
        股票代码标准化适配。
        
        Args:
            std_code: 标准格式股票代码（如 600000.SH）
        
        Returns:
            适配 baostock 接口的格式（如 sh.600000）
        """
        # 先标准化为后缀格式
        suffix_code = normalize_stock_code(std_code, StockCodeFormat.SUFFIX)
        code, market = suffix_code.split(".")
        
        # 转换为 baostock 格式: 市场小写在前，点分隔
        market_lower = market.lower()
        return f"{market_lower}.{code}"

    def _convert_index_code(self, std_code: str) -> str:
        """
        指数代码标准化适配。
        
        Args:
            std_code: 标准格式指数代码
        
        Returns:
            适配 baostock 接口的格式
        """
        # baostock 指数格式与股票相同
        return self._convert_stock_code(std_code)

    def _convert_trade_date(self, std_date: str) -> str:
        """
        日期标准化适配。
        
        Args:
            std_date: 标准格式日期（如 2024-01-01）
        
        Returns:
            适配 baostock 接口的纯数字格式日期（如 2024-01-01，baostock 支持连字符格式）
        """
        # baostock 支持 YYYY-MM-DD 格式
        return normalize_trade_date(std_date, TradeDateFormat.HYPHEN)

    def _convert_kline_period(self, period: KlinePeriod) -> str:
        """
        K线周期适配。
        
        Args:
            period: 标准 KlinePeriod 枚举
        
        Returns:
            baostock 周期代码
        """
        period_mapping = {
            KlinePeriod.DAY: "d",
            KlinePeriod.WEEK: "w",
            KlinePeriod.MONTH: "m",
        }
        result = period_mapping.get(period, "d")
        if period not in period_mapping:
            logger.warning(f"[Baostock] 不支持的周期 {period}，使用日线(d)")
        return result

    def _convert_divid_type(self, adjust: DividendType) -> str:
        """
        复权类型适配。
        
        Args:
            adjust: 标准 DividendType 枚举
        
        Returns:
            baostock 复权参数
        """
        adjust_mapping = {
            DividendType.NONE: "3",  # 不复权
            DividendType.FRONT: "2",  # 前复权
            DividendType.BACK: "1",   # 后复权
        }
        result = adjust_mapping.get(adjust, "3")
        return result

    def get_trade_date(self, start_date: str, end_date: str) -> pa.Table:
        """
        获取指定时间段内的交易日列表。
        
        Args:
            start_date: 开始日期（标准化格式：YYYY-MM-DD）
            end_date: 结束日期（标准化格式：YYYY-MM-DD）
        
        Returns:
            PyArrow Table，包含交易日数据
        
        Note:
            baostock 没有直接的交易日历接口，返回空表
        """
        logger.warning("[Baostock] 暂不支持交易日历接口")
        return pa.table(
            {"trade_date": []},
            schema=TRADEDATE_PA_SCHEMA
        )

    def get_stock_list(self) -> List[Stock]:
        """
        获取全市场股票列表（基础信息）。
        
        Returns:
            List[Stock]: 股票模型列表，包含代码、名称等基础信息
        """
        self._ensure_connected()
        
        try:
            # 查询上证和深证的股票
            stocks = []
            
            for market in ["sh", "sz"]:
                rs = self._bs.query_all_stock(day=datetime.now().strftime("%Y-%m-%d"))
                if rs.error_code != "0":
                    logger.error(f"[Baostock] 获取 {market} 股票列表失败: {rs.error_msg}")
                    continue
                
                while (rs.error_code == "0") & rs.next():
                    row = rs.get_row_data()
                    code = row[0]
                    
                    # 查询详细信息
                    detail_rs = self._bs.query_stock_basic(code=code)
                    if detail_rs.error_code != "0":
                        continue
                    
                    if detail_rs.next():
                        detail = detail_rs.get_row_data()
                        stock = Stock(
                            code=detail[0].split(".")[1],  # 去掉市场前缀
                            name=detail[1],
                            industry=detail[2] if detail[2] else None,
                            list_date=datetime.strptime(detail[5], "%Y-%m-%d").date() if detail[5] else None,
                        )
                        stocks.append(stock)
            
            logger.success(f"[Baostock] 获取股票列表成功: 共 {len(stocks)} 条")
            return stocks
            
        except Exception as e:
            logger.error(f"[Baostock] 获取股票列表失败: {str(e)}")
            raise DataSourceException(f"[Baostock] 获取股票列表失败: {str(e)}")

    def get_index_list(self) -> List:
        """
        获取全市场指数列表。
        
        Returns:
            指数列表
        
        Note:
            baostock 指数查询接口有限
        """
        logger.warning("[Baostock] 指数列表接口暂未实现")
        return []

    def get_kline_data(
        self,
        code: str,
        start_date: str,
        end_date: str,
        period: KlinePeriod = KlinePeriod.DAY,
        adjust: DividendType = DividendType.NONE,
    ) -> pa.Table:
        """
        获取指定股票的 K 线数据。
        
        Args:
            code: 股票代码（标准化格式）
            start_date: 开始日期（标准化格式：YYYY-MM-DD）
            end_date: 结束日期（标准化格式：YYYY-MM-DD）
            period: K线周期
            adjust: 复权类型
        
        Returns:
            PyArrow Table，包含日线数据
        """
        self._ensure_connected()
        
        try:
            # 转换代码和日期格式
            bs_code = self._convert_stock_code(code)
            bs_start = self._convert_trade_date(start_date)
            bs_end = self._convert_trade_date(end_date)
            bs_period = self._convert_kline_period(period)
            bs_adjust = self._convert_divid_type(adjust)
            
            # 调用 baostock 接口
            rs = self._bs.query_history_k_data_plus(
                bs_code,
                "date,code,open,high,low,close,preclose,volume,amount,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                start_date=bs_start,
                end_date=bs_end,
                frequency=bs_period,
                adjustflag=bs_adjust,
            )
            
            if rs.error_code != "0":
                raise DataSourceException(f"[Baostock] 查询K线失败: {rs.error_msg}")
            
            # 收集数据
            data = []
            while (rs.error_code == "0") & rs.next():
                row = rs.get_row_data()
                data.append({
                    "code": row[1].split(".")[1] if "." in row[1] else row[1],
                    "trade_date": row[0],
                    "open": float(row[2]) if row[2] else None,
                    "high": float(row[3]) if row[3] else None,
                    "low": float(row[4]) if row[4] else None,
                    "close": float(row[5]) if row[5] else None,
                    "preclose": float(row[6]) if row[6] else None,
                    "volume": float(row[7]) if row[7] else None,
                    "amount": float(row[8]) if row[8] else None,
                    "turn": float(row[9]) if row[9] else None,
                })
            
            # 转换为 PyArrow Table
            if data:
                df = pd.DataFrame(data)
                table = pa.Table.from_pandas(df, schema=STOCKDAILY_PA_SCHEMA)
            else:
                table = pa.table(
                    {
                        "code": [],
                        "trade_date": [],
                        "open": [],
                        "high": [],
                        "low": [],
                        "close": [],
                        "preclose": [],
                        "volume": [],
                        "amount": [],
                        "turn": [],
                    },
                    schema=STOCKDAILY_PA_SCHEMA
                )
            
            logger.success(f"[Baostock] 获取 {code} K线数据成功: 共 {len(data)} 条")
            return table
            
        except Exception as e:
            logger.error(f"[Baostock] 获取K线数据失败: {str(e)}")
            raise DataSourceException(f"[Baostock] 获取K线数据失败: {str(e)}")

    def get_stock_daily(self, code: str, start_date: str, end_date: str) -> pa.Table:
        """
        获取指定股票在指定时间段内的日线行情数据。
        
        Args:
            code: 股票代码（标准化格式）
            start_date: 开始日期（标准化格式：YYYY-MM-DD）
            end_date: 结束日期（标准化格式：YYYY-MM-DD）
        
        Returns:
            PyArrow Table，包含日线数据
        """
        return self.get_kline_data(code, start_date, end_date)

    def get_all_stock_daily(self, trade_date: str) -> pa.Table:
        """
        获取全市场股票的日线数据。
        
        Args:
            trade_date: 交易日期（标准化格式：YYYY-MM-DD）
        
        Returns:
            PyArrow Table
        
        Note:
            baostock 不支持批量获取，需逐个股票查询（不推荐）
        """
        logger.warning("[Baostock] 全市场日线数据接口暂未实现（建议逐个股票查询）")
        return pa.table(
            {
                "code": [],
                "trade_date": [],
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
                "amount": [],
            },
            schema=STOCKDAILY_PA_SCHEMA
        )

    def get_stock_div(self, code: str, start_date: str, end_date: str) -> pa.Table:
        """
        获取指定时间段的除权除息数据。
        
        Args:
            code: 股票代码（标准化格式）
            start_date: 开始日期（标准化格式：YYYY-MM-DD）
            end_date: 结束日期（标准化格式：YYYY-MM-DD）
        
        Returns:
            PyArrow Table
        """
        logger.warning("[Baostock] 除权除息接口暂未实现")
        return pa.table({})

    def get_capital_daily(self, code: str, trade_date: str):
        """
        获取股本数据。
        
        Note:
            baostock 没有专门的股本接口
        """
        logger.warning("[Baostock] 股本数据接口暂未实现")
        return None

    def get_index_daily(self, code: str, start_date: str, end_date: str) -> pa.Table:
        """
        获取指定指数在指定时间段内的日线行情数据。
        
        Args:
            code: 指数代码（标准化格式）
            start_date: 开始日期（标准化格式：YYYY-MM-DD）
            end_date: 结束日期（标准化格式：YYYY-MM-DD）
        
        Returns:
            PyArrow Table，包含日线数据
        
        Note:
            baostock 指数数据有限
        """
        logger.warning("[Baostock] 指数日线接口暂未实现")
        import pyarrow as pa
        from quantss.models import INDEXDAILY_PA_SCHEMA
        return pa.table(
            {"code": [], "trade_date": [], "open": [], "high": [], "low": [], "close": [], "volume": [], "amount": []},
            schema=INDEXDAILY_PA_SCHEMA
        )
