"""
除权除息模型模块
================

定义股票除权除息数据模型。
"""

from sqlmodel import Field, SQLModel
from typing import ClassVar, Optional
from datetime import date
from quantss.common import DbTable
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin


class StockDividend(ArrowSchemaMixin, SQLModel, table=True):
    """
    股票除权除息表。
    
    存储股票的除权除息数据，包括分红、转股、配股等信息。
    """
    
    TABLE: ClassVar[str] = DbTable.STOCK_DIVIDEND.value
    CODE: ClassVar[str] = "code"
    TRADE_DATE: ClassVar[str] = "trade_date"
    CATEGORY: ClassVar[str] = "category"
    DIVIDEND: ClassVar[str] = "dividend"
    BONUS_RATIO: ClassVar[str] = "bonus_ratio"
    RIGHTS_RATIO: ClassVar[str] = "rights_ratio"
    RIGHTS_PRICE: ClassVar[str] = "rights_price"

    __tablename__ = TABLE

    code: str = Field(primary_key=True, max_length=6, description="股票代码")
    trade_date: date = Field(primary_key=True, description="除权除息日")
    category: Optional[str] = Field(max_length=10, description="除权除息类型")
    dividend: float = Field(max_digits=10, decimal_places=4, description="分红")
    bonus_ratio: float = Field(max_digits=10, decimal_places=4, description="转股")
    rights_ratio: float = Field(max_digits=10, decimal_places=4, description="配股")
    rights_price: float = Field(max_digits=10, decimal_places=2, description="配股价")

    model_config = {"unique_keys": ["code", "trade_date"]}

