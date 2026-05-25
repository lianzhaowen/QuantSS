import pyarrow as pa

from quantss.models.qfq_stock_daily_view import QfqStockDailyView
from quantss.models.stock import Stock
from quantss.models.stock_dividend_view import StockDividendView
from quantss.models.trade_date import TradeDate
from quantss.models.stock_daily import StockDaily
from quantss.models.stock_dividend import StockDividend
from quantss.models.capital_daily import CapitalDaily
from quantss.models.stock_view import StockView
from quantss.models.index import Index
from quantss.models.index_daily import IndexDaily
from quantss.models.index_view import IndexView

# ==================== 1. 显式声明全局 Schema 变量 (保障 IDE 补全与静态提示) =========
STOCK_PA_SCHEMA: "pa.Schema"
TRADEDATE_PA_SCHEMA: "pa.Schema"
STOCKDAILY_PA_SCHEMA: "pa.Schema"
STOCKDIVIDEND_PA_SCHEMA: "pa.Schema"
CAPITALDAILY_PA_SCHEMA: "pa.Schema"
INDEX_PA_SCHEMA: "pa.Schema"
INDEXDAILY_PA_SCHEMA: "pa.Schema"
STOCKVIEW_PA_SCHEMA: "pa.Schema"
INDEXVIEW_PA_SCHEMA: "pa.Schema"
STOCKDIVIDENDVIEW_PA_SCHEMA: "pa.Schema"
QFQSTOCKDAILYVIEW_PA_SCHEMA: "pa.Schema"


# 模型聚合列表
ALL_MODELS = [
    Stock,
    TradeDate,
    StockDaily,
    StockDividend,
    CapitalDaily,
    Index,
    IndexDaily,
    StockDividendView,
    StockView,
    IndexView,
    QfqStockDailyView,
]

# ==================== 2. 自动化批量生成与赋值核心逻辑 ====================
for model in ALL_MODELS:
    # 动态构建标准的全局变量命名（例如: Stock -> STOCK_PA_SCHEMA）
    var_name = f"{model.__name__.upper()}_PA_SCHEMA"
    
    # 动态将生成的 PyArrow Schema 注入到当前模块全局命名空间中
    globals()[var_name] = model.sqlmodel_to_pa_schema()

__all__ = [
    "Stock",
    "TradeDate",
    "StockDaily",
    "StockDividend",
    "CapitalDaily",
    "Index",
    "IndexDaily",
    "StockView",
    "IndexView",
    "StockDividendView",
    "QfqStockDailyView",
    "ALL_MODELS",
]