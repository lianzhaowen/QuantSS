import pyarrow as pa

from abc import ABC, abstractmethod
from typing import List
from quantss.models import CapitalDaily, IndexDaily, Stock, StockDaily, TradeDate, StockDividend, Index
from quantss.common import KlinePeriod, DividendType

class BaseDataSource(ABC):

    def __init__(self):
        self.connected = False

    def connect(self) -> None:
        """【模板方法】统一的连接入口，控制状态机并分发具体的物理连接"""
        if self.connected:
            return
        
        self._connect()
        self.connected = True

    def disconnect(self) -> None:
        """【模板方法】统一的断开入口"""
        if not self.connected:
            return

        self._disconnect()
        self.connected = False

    @abstractmethod
    def _connect(self) -> None:
        """由具体的数据库子类去实现真正的驱动连接细节"""
        pass

    @abstractmethod
    def _disconnect(self) -> None:
        """由具体的数据库子类去实现真正的驱动断开细节"""
        pass

    @abstractmethod
    def _convert_stock_code(self, std_code: str) -> str:
        """
        适配标准化股票代码为数据源专属格式（内部方法）。
        
        不同数据源的股票代码格式可能不同（如是否带后缀、市场标识位置等），
        子类需实现此方法完成标准化代码到数据源代码的转换。
        
        Args:
            std_code: 标准化股票代码（如 "600000.SH"）
        
        Returns:
            str: 适配后数据源可识别的股票代码
        """
        pass

    @abstractmethod
    def _convert_trade_date(self, std_date: str) -> str:
        """
        适配标准化日期格式为数据源专属格式（内部方法）。
        
        不同数据源的日期格式可能不同（如 "YYYY-MM-DD" / "YYYYMMDD"），
        子类需实现此方法完成标准化日期到数据源日期的转换。
        
        Args:
            std_date: 标准化日期字符串（格式：YYYY-MM-DD）
        
        Returns:
            str: 适配后数据源可识别的日期字符串
        """
        pass

    @abstractmethod
    def _convert_kline_period(self, period: KlinePeriod) -> str:
        pass

    @abstractmethod
    def _convert_divid_type(self, adjust: DividendType) -> str:
        pass

    @abstractmethod
    def get_trade_date(self, start_date: str, end_date: str) -> pa.Table:
        """
        获取指定时间段内的交易日列表。
        
        Args:
            start_date: 开始日期（标准化格式：YYYY-MM-DD）
            end_date: 结束日期（标准化格式：YYYY-MM-DD）
        
        Returns:
            List[TradeDate]: 交易日模型列表，每个元素包含 trade_date 等字段
        """
        pass

    @abstractmethod
    def get_stock_list(self) -> List[Stock]:
        """
        获取全市场股票列表（基础信息）。
        
        Returns:
            List[Stock]: 股票模型列表，包含代码、名称、上市日期等基础信息
        """
        pass

    @abstractmethod
    def get_stock_daily(self, code: str, start_date: str, end_date: str) -> pa.Table:
        """
        获取指定股票在指定时间段内的日线行情数据。
        
        Args:
            code: 标准化股票代码（如 "600000.SH"）
            start_date: 开始日期（标准化格式：YYYY-MM-DD）
            end_date: 结束日期（标准化格式：YYYY-MM-DD）
        
        Returns:
            List[StockDaily]: 股票日线模型列表，包含开盘价、收盘价、成交量等字段
        """
        pass

    @abstractmethod
    def get_index_list(self) -> List[Index]:
        """
        获取全市场指数列表（基础信息）。
        
        Returns:
            List[Index]: 股票模型列表，包含代码、名称、上市日期等基础信息
        """
        pass

    @abstractmethod
    def get_index_daily(self, code: str, start_date: str, end_date: str) -> pa.Table:
        """
        获取指定指数在指定时间段内的日线行情数据。
        
        Args:
            code: 标准化股票代码（如 "600000.SH"）
            start_date: 开始日期（标准化格式：YYYY-MM-DD）
            end_date: 结束日期（标准化格式：YYYY-MM-DD）
        
        Returns:
            List[IndexDaily]: 股票日线模型列表，包含开盘价、收盘价、成交量等字段
        """
        pass

    @abstractmethod
    def get_divid_factor(self, code: str, start_date: str, end_date: str) -> pa.Table:
        """
        获取指定股票在指定时间段内的除权除息因子。
        
        Args:
            code: 标准化股票代码（如 "600000.SH"）
            start_date: 开始日期（标准化格式：YYYY-MM-DD）
            end_date: 结束日期（标准化格式：YYYY-MM-DD）
        
        Returns:
            List[StockDividend]: 除权除息模型列表，包含送股、转增、分红等因子字段
        """
        pass

    @abstractmethod
    def get_capital_daily(self, code: str, start_date: str, end_date: str) -> pa.Table:
        """
        获取指定股票在指定时间段内的资金流向相关数据。
        
        Args:
            code: 标准化股票代码（如 "600000.SH"）
            start_date: 开始日期（标准化格式：YYYY-MM-DD）
            end_date: 结束日期（标准化格式：YYYY-MM-DD）
        
        Returns:
            pa.Table: 资金数据列表，包含总股本、流通股本等字段
        """
        pass