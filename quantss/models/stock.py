"""
股票模型模块
============

定义股票基础信息数据模型。
"""

from typing import ClassVar
from sqlmodel import Field, SQLModel
from quantss.common import DbTable
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin


class Stock(ArrowSchemaMixin, SQLModel, table=True):
    """
    股票基础信息表。
    
    存储股票的基本信息，包括股票代码和名称。
    """

    TABLE: ClassVar[str] = DbTable.STOCK_LIST.value
    CODE: ClassVar[str] = "code"
    NAME: ClassVar[str] = "name"    

    __tablename__ = TABLE

    code: str = Field(primary_key=True, max_length=6, description="股票代码")
    name: str = Field(max_length=100, description="股票名称")

    model_config = {"unique_keys": ["code"]}

