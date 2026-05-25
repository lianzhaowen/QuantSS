"""
指数视图模型模块
===============

定义指数数据联合查询视图，关联指数基础信息和日线行情。
"""

from datetime import date
from typing import ClassVar
from sqlmodel import SQLModel, select
from quantss.common.enums import DbView
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin
from quantss.models.index import Index
from quantss.models.index_daily import IndexDaily


class IndexView(ArrowSchemaMixin, SQLModel, table=False):
    """
    指数数据联合视图。
    
    关联指数基础信息表和日线行情表，提供完整的指数数据查询视图。
    """

    code: str
    name: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float

    # SQL 查询语句作为类属性（ClassVar 标记避免被当作字段）
    stmt: ClassVar = select(
        IndexDaily.code,           # 股票代码（日线表）
        Index.name,                # 股票名称（基础信息表）
        IndexDaily.trade_date,     # 交易日期（日线表）
        IndexDaily.open,           # 开盘价
        IndexDaily.high,           # 最高价
        IndexDaily.low,            # 最低价
        IndexDaily.close,          # 收盘价
        IndexDaily.volume,         # 成交量
        IndexDaily.amount,         # 成交额
    ).select_from(IndexDaily) \
    .join(Index, Index.code == IndexDaily.code)

    # Pydantic V2 配置
    model_config = {"__viewname__": DbView.INDEX_VIEW.value}