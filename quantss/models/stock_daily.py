"""
股票日线行情模型模块
====================

定义股票日线行情数据模型。
"""

from typing import ClassVar
from sqlmodel import Field, SQLModel
from datetime import date
from quantss.common import DbTable
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin


class StockDaily(ArrowSchemaMixin, SQLModel, table=True):
    """
    股票日线行情表。
    
    存储股票的每日行情数据，包括开盘价、最高价、最低价、收盘价、成交量和成交额。
    """

    TABLE: ClassVar[str] = DbTable.STOCK_DAILY.value
    CODE: ClassVar[str] = "code"
    TRADE_DATE: ClassVar[str] = "trade_date"
    OPEN: ClassVar[str] = "open"
    HIGH: ClassVar[str] = "high"
    LOW: ClassVar[str] = "low"
    CLOSE: ClassVar[str] = "close"
    VOLUME: ClassVar[str] = "volume"
    AMOUNT: ClassVar[str] = "amount"

    __tablename__ = TABLE

    code: str = Field(primary_key=True, max_length=6, description="股票代码")
    trade_date: date = Field(primary_key=True, description="交易日期")
    open: float = Field(default=None, description="开盘价")
    high: float = Field(default=None, description="最高价")
    low: float = Field(default=None, description="最低价")
    close: float = Field(default=None, description="收盘价")
    volume: float = Field(default=None, description="成交量")
    amount: float = Field(default=None, description="成交额")

    model_config = {"unique_keys": ["code", "trade_date"]}
