"""
股票分红视图模块
===============

定义股票分红计算视图，用于计算复权因子和前复权价格。
"""

from typing import ClassVar
from sqlmodel import SQLModel, func, select
from sqlalchemy import case
from quantss.common.enums import DbView
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin
from quantss.models.stock_daily import StockDaily
from quantss.models.stock_dividend import StockDividend


# 第一层 CTE：基础数据对齐、单位换算与前日收盘价 (lag)
pre_close_expr = func.lag(StockDaily.close).over(
    partition_by=StockDaily.code,
    order_by=StockDaily.trade_date.asc()
)

first_stmt = select(
    StockDaily.code,
    StockDaily.trade_date,
    StockDaily.close,
    StockDaily.open,
    (func.coalesce(StockDividend.dividend, 0) / 10.0).label("D"),
    (func.coalesce(StockDividend.bonus_ratio, 0) / 10.0).label("BR"),
    (func.coalesce(StockDividend.rights_ratio, 0) / 10.0).label("RR"),
    func.coalesce(StockDividend.rights_price, 0).label("RP"),
    pre_close_expr.label("P")
).select_from(StockDaily).join(
    StockDividend, (StockDividend.code == StockDaily.code) & (StockDividend.trade_date == StockDaily.trade_date), isouter=True
).cte("first_data")

# =========================================================================
# 【第二层 CTE】核心计算：除权价与单次调整系数 (adjust_ratio)
# =========================================================================
p_safe = func.coalesce(
    case((first_stmt.c.P > 0, first_stmt.c.P), else_=None), 
    first_stmt.c.open
)
denominator_expr = 1.0 + first_stmt.c.BR + first_stmt.c.RR
denominator_clipped = case((denominator_expr >= 1.0, denominator_expr), else_=1.0)
ex_right_price_expr = (p_safe - first_stmt.c.D + (first_stmt.c.RR * first_stmt.c.RP)) / denominator_clipped

second_stmt = select(
    first_stmt.c.code,
    first_stmt.c.trade_date,
    first_stmt.c.close,
    first_stmt.c.P,
    (ex_right_price_expr / p_safe).label("adjust_ratio")
).cte("second_data")

# =========================================================================
# 🔥【第三层 CTE（新增）】破除窗口嵌套！专门计算移位后的 adjust_aligned (shift(-1))
# =========================================================================
adjust_aligned_expr = func.lead(second_stmt.c.adjust_ratio, 1).over(
    partition_by=second_stmt.c.code,
    order_by=second_stmt.c.trade_date.asc()
)

third_stmt = select(
    second_stmt.c.code,
    second_stmt.c.trade_date,
    second_stmt.c.close,
    second_stmt.c.P.label("pre_close"),
    second_stmt.c.adjust_ratio,
    # 在这一层先用 lead 把明天的数据拿到今天，并做 fillna(1.0) 填充
    func.coalesce(adjust_aligned_expr, 1.0).label("adjust_aligned")
).cte("third_data")

# =========================================================================
# 【第四层 最外层 SELECT】无污染安全进行对数反向累乘计算前复权因子
# =========================================================================
fourth_stmt = select(
    third_stmt.c.code,
    third_stmt.c.trade_date,
    third_stmt.c.close,
    third_stmt.c.pre_close,
    third_stmt.c.adjust_ratio,
    func.exp(
        func.sum(
            case(
                (third_stmt.c.adjust_aligned > 0, func.ln(third_stmt.c.adjust_aligned)),
                else_=0.0
            )
        ).over(
            partition_by=third_stmt.c.code,
            order_by=third_stmt.c.trade_date.asc(),
            rows=(0, None)  # CURRENT ROW TO UNBOUNDED FOLLOWING
        )
    ).label("qfq_factor")
)

# =========================================================================
# 视图映射声明
# =========================================================================
class StockDividendView(ArrowSchemaMixin, SQLModel, table=False):
    """
    股票分红视图。
    
    用于计算复权因子和前复权价格，关联股票日线数据和分红数据。
    """

    code: str
    trade_date: str
    close: float
    pre_close: float | None
    adjust_ratio: float
    qfq_factor: float

    # SQL 查询语句作为类属性（ClassVar 标记避免被当作字段）
    stmt: ClassVar = fourth_stmt

    # Pydantic V2 配置
    model_config = {"__viewname__": DbView.STOCK_DIVIDEND_VIEW.value}