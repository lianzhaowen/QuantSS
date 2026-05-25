"""
每日股本模型模块
================

定义每日股本数据模型。
"""

from typing import ClassVar
from sqlmodel import Field, SQLModel
from datetime import date
from quantss.common import DbTable
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin


class CapitalDaily(ArrowSchemaMixin, SQLModel, table=True):
    """
    每日股本表。
    
    存储股票的每日股本数据，包括总股本和流通股本。
    """

    TABLE: ClassVar[str] = DbTable.CAPITAL_DAILY.value
    CODE: ClassVar[str] = "code"
    TRADE_DATE: ClassVar[str] = "trade_date"
    TOTAL_SHARE: ClassVar[str] = "total_share"
    FLOAT_SHARE: ClassVar[str] = "float_share"

    __tablename__ = TABLE

    code: str = Field(primary_key=True, max_length=6, description="股票代码")
    trade_date: date = Field(primary_key=True, description="交易日期")
    total_share: float = Field(default=None, description="总股本")
    float_share: float = Field(default=None, description="流通股本")

    model_config = {"unique_keys": ["code", "trade_date"]}
