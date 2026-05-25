"""
股票视图模型模块
===============

定义股票数据联合查询视图，关联股票基础信息、日线行情和股本数据。
"""

from datetime import date
from typing import ClassVar
from sqlmodel import SQLModel, select
from quantss.common.enums import DbView
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin
from quantss.models.stock import Stock
from quantss.models.stock_daily import StockDaily
from quantss.models.capital_daily import CapitalDaily


class StockView(ArrowSchemaMixin, SQLModel, table=False):
    """
    股票数据联合视图。
    
    关联股票基础信息表、日线行情表和每日股本表，提供完整的股票数据查询视图。
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
    total_share: float
    float_share: float

    # SQL 查询语句作为类属性（ClassVar 标记避免被当作字段）
    stmt: ClassVar = select(
        StockDaily.code,           # 股票代码（日线表）
        Stock.name,                # 股票名称（基础信息表）
        StockDaily.trade_date,     # 交易日期（日线表）
        StockDaily.open,           # 开盘价
        StockDaily.high,           # 最高价
        StockDaily.low,            # 最低价
        StockDaily.close,          # 收盘价
        StockDaily.volume,         # 成交量
        StockDaily.amount,         # 成交额
        CapitalDaily.total_share,  # 总股本（每日股本表）
        CapitalDaily.float_share,  # 流通股本（每日股本表）
    ).select_from(StockDaily) \
    .join(Stock, Stock.code == StockDaily.code) \
    .join(CapitalDaily, (CapitalDaily.code == StockDaily.code) & (CapitalDaily.trade_date == StockDaily.trade_date))

    # Pydantic V2 配置
    model_config = {"__viewname__": DbView.STOCK_VIEW.value}