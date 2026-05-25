"""
前复权日线视图模型模块
======================

定义前复权股票日线数据视图，包含复权因子计算和价格调整。
"""

from datetime import date
from typing import ClassVar
from sqlmodel import SQLModel, select, text

from quantss.common.enums import DbView
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin


class QfqStockDailyView(ArrowSchemaMixin, SQLModel, table=False):
    """
    前复权股票日线数据视图。
    
    提供前复权后的股票日线数据，包含复权因子和调整后的价格、成交量、成交额。
    """

    TABLE: ClassVar[str] = DbView.QFQ_STOCK_DAILY_VIEW.value
    CODE: ClassVar[str] = "code"
    TRADE_DATE: ClassVar[str] = "trade_date"
    OPEN: ClassVar[str] = "open"
    HIGH: ClassVar[str] = "high"
    LOW: ClassVar[str] = "low"
    CLOSE: ClassVar[str] = "close"
    VOLUME: ClassVar[str] = "volume"
    AMOUNT: ClassVar[str] = "amount"
    TOTAL_SHARE: ClassVar[str] = "total_share"
    FLOAT_SHARE: ClassVar[str] = "float_share"
    QFQ_FACTOR: ClassVar[str] = "qfq_factor"
    ADJ_OPEN: ClassVar[str] = "adj_open"
    ADJ_HIGH: ClassVar[str] = "adj_high" 
    ADJ_LOW: ClassVar[str] = "adj_low"
    ADJ_CLOSE: ClassVar[str] = "adj_close"
    ADJ_VOLUME: ClassVar[str] = "adj_volume"
    ADJ_AMOUNT: ClassVar[str] = "adj_amount"

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
    qfq_factor: float
    adj_open: float
    adj_high: float 
    adj_low: float
    adj_close: float
    adj_volume: float
    adj_amount: float

    # SQL 查询语句作为类属性（ClassVar 标记避免被当作字段）
    # 涉及到 view 的嵌套，改用 text 这种方式延迟加载 ！！！
    # 修正表名为数据库中实际存在的物理表名
    stmt: ClassVar = select(
        text("stock_daily.code AS code"),
        text("stock_list.name AS name"), 
        text("stock_daily.trade_date AS trade_date"),
        text("stock_daily.open AS open"),
        text("stock_daily.high AS high"),
        text("stock_daily.low AS low"),
        text("stock_daily.close AS close"),
        text("stock_daily.volume AS volume"),
        text("stock_daily.amount AS amount"),
        text("capital_daily.total_share AS total_share"),
        text("capital_daily.float_share AS float_share"),
        text("stock_dividend_view.qfq_factor AS qfq_factor"),
        text("stock_daily.open * stock_dividend_view.qfq_factor AS adj_open"),
        text("stock_daily.high * stock_dividend_view.qfq_factor AS adj_high"),
        text("stock_daily.low * stock_dividend_view.qfq_factor AS adj_low"),
        text("stock_daily.close * stock_dividend_view.qfq_factor AS adj_close"),
        text("stock_daily.volume / stock_dividend_view.qfq_factor AS adj_volume"),
        text("stock_daily.amount / stock_dividend_view.qfq_factor AS adj_amount"),
    ).select_from(text("stock_daily")) \
    .join(text("stock_list"), text("stock_list.code = stock_daily.code")) \
    .join(text("capital_daily"), text("capital_daily.code = stock_daily.code AND capital_daily.trade_date = stock_daily.trade_date")) \
    .join(text("stock_dividend_view"), text("stock_dividend_view.code = stock_daily.code AND stock_dividend_view.trade_date = stock_daily.trade_date"))

    # Pydantic V2 配置
    model_config = {"__viewname__": "qfq_stock_daily_view"}