"""
指数模型模块
============

定义指数基础信息数据模型。
"""

from typing import ClassVar
from sqlmodel import Field, SQLModel
from quantss.common import DbTable
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin


class Index(ArrowSchemaMixin, SQLModel, table=True):
    """
    指数基础信息表。
    
    存储指数的基本信息，包括指数代码和名称。
    """

    TABLE: ClassVar[str] = DbTable.INDEX_LIST.value
    CODE: ClassVar[str] = "code"
    NAME: ClassVar[str] = "name"    

    __tablename__ = TABLE

    code: str = Field(primary_key=True, max_length=6, description="指数代码")
    name: str = Field(max_length=100, description="指数名称")

    model_config = {"unique_keys": ["code"]}

