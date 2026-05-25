"""
交易日历模型模块
================

定义交易日历数据模型。
"""

from typing import ClassVar
from sqlmodel import Field, SQLModel
from datetime import date
from quantss.common import DbTable
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin


class TradeDate(ArrowSchemaMixin, SQLModel, table=True):
    """
    交易日历表。
    
    存储A股市场的交易日历数据。
    """

    TABLE: ClassVar[str] = DbTable.TRADE_DATE.value
    TRADE_DATE: ClassVar[str] = "trade_date"

    __tablename__ = TABLE

    trade_date: date = Field(primary_key=True, description="交易日期")

    model_config = {"unique_keys": ["trade_date"]}


