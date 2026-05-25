"""
数据工具模块
============

提供股票数据查询和处理的工具函数。
"""

import streamlit as st
import polars as pl

from quantss.manager import database
from quantss.models import IndexDaily, QfqStockDailyView, Stock, StockDaily
from quantss.utils.indicator import CCI, KDJ, MA, MACD, RSI, W_JX, BIAS, W_GL, W_TD
import polars.selectors as cs

def init_page_config():
    """
    初始化 Streamlit 页面配置。
    
    设置页面标题、图标、布局等全局配置，并隐藏默认的导航元素。
    """
    st.set_page_config(
        page_title="股票数据系统",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    HIDE_STYLE = """
        <style>
        /* 隐藏顶部导航、页脚、菜单 */
        header, footer, #MainMenu {visibility: hidden !important; height: 0 !important;}
        /* 强制隐藏原生侧边栏的页面导航 */
        [data-testid="stSidebarNav"] {display: none !important;}
        [data-testid="stSidebarNavItems"] {display: none !important;}
        .css-1v8ivcs {display: none !important;}
        .css-1oe09kw {display: none !important;}
        /* 清理侧边栏空白 */
        section[data-testid="stSidebar"] .css-ng1t4o {padding-top: 1rem !important;}
        </style>
    """
    st.markdown(HIDE_STYLE, unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def get_stock_list() -> pl.DataFrame:
    """
    获取股票列表。
    
    Returns:
        polars.DataFrame: 按代码排序的股票列表
    """
    df = pl.from_arrow(database.select(model_cls=Stock))
    return df.sort(Stock.CODE)

@st.cache_data(ttl=3600)
def calculate_indicator(df) -> pl.DataFrame:
    OPEN, CLOSE, HIGH, LOW, VOLUME, AMOUNT = (
        pl.col("adj_open"), pl.col("adj_close"), pl.col("adj_high"),
        pl.col("adj_low"), pl.col("adj_volume"), pl.col("adj_amount")
    )
    periods = [5, 10, 20, 30, 60, 120, 250]

    # 计算多输出指标
    dif, dea, macd = MACD(CLOSE, 12, 26, 9)
    k, d, j = KDJ(CLOSE, HIGH, LOW, 9, 3, 3)
    bias60, bias120, bias250 = BIAS(CLOSE, 60, 120, 250)
    jxb, jxt = W_JX(OPEN, HIGH, LOW, CLOSE)

    return (
        df
        .drop_nulls(subset=["open", "close", "high", "low"])
        .sort("trade_date")
        .with_columns(
            # 基础字段清洗与衍生
            pl.col("trade_date").dt.to_string("%Y-%m-%d"),
            adj_volume=VOLUME / 1_000_000,
            adj_amount=AMOUNT / 10_000,
            pct_chg=CLOSE.pct_change() * 100,

            # 批量 MA 均线注入
            *[MA(CLOSE, p).alias(f"MA{p}") for p in periods],

            # 经典技术指标全平铺
            RSI=RSI(CLOSE, 14),
            DIF=dif, DEA=dea, MACD=macd,
            K=k, D=d, J=j,
            CCI=CCI(CLOSE, HIGH, LOW, 14),
            BIAS60=bias60, BIAS120=bias120, BIAS250=bias250,
            JXB=jxb,
            JXT=jxt,
        )
        .with_columns(
            VOL5=MA(VOLUME, 5),
            VOL34=MA(VOLUME, 34)
        )
        .with_columns(
            cs.numeric().exclude(["trade_date", "code", "name"]).round(2)
        )
    )

@st.cache_data(ttl=3600)
def get_stock_daily(code, start_date, end_date) -> pl.DataFrame:
    """
    获取股票日线数据。
    
    Args:
        code: 股票代码
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        polars.DataFrame: 按日期排序的日线数据
    """
    df = pl.from_arrow(
        database.select(
            model_cls=QfqStockDailyView,
            filters=[
                (QfqStockDailyView.CODE, "=", code),
                (QfqStockDailyView.TRADE_DATE, ">=", start_date),
                (QfqStockDailyView.TRADE_DATE, "<=", end_date)
            ],
        )
    ).sort(StockDaily.TRADE_DATE)

    return calculate_indicator(df)


@st.cache_data(ttl=3600)
def get_latest_data_date():
    """
    获取最新数据日期。
    
    Returns:
        最新交易日期
    """
    table = database.aggregate(
        model_cls=StockDaily,
        agg_exprs={"result": f"MAX({StockDaily.TRADE_DATE})"},
    )
    
    # 2. 检查表是否为空
    if table.num_rows == 0:
        return None
        
    # 3. 从中提取具体数值
    # ["last_sync_date"] 获取对应列，[0] 获取第一行，as_py() 转换为 Python 原生类型
    result = table["result"][0].as_py()
    return result

@st.cache_data(ttl=3600)
def get_total_stock_count():
    """
    获取股票总数。
    
    Returns:
        股票数量
    """
    table = database.aggregate(
        model_cls=Stock,
        agg_exprs={"result": f"COUNT({Stock.CODE})"},
    )
    if table.num_rows == 0:
        return None
    result = table["result"][0].as_py()
    return result


@st.cache_data(ttl=3600)
def get_total_kline_count():
    """
    获取 K 线数据总数。
    
    Returns:
        K 线数据数量
    """
    table = database.aggregate(
        model_cls=StockDaily,
        agg_exprs={"result": f"COUNT({StockDaily.CODE})"},
    )
    if table.num_rows == 0:
        return None
    result = table["result"][0].as_py()
    return result


@st.cache_resource(ttl=3600)
def get_all_stock_daily(start_date=None, end_date=None) -> pl.DataFrame:
    """
    获取所有股票日线数据。
    
    Args:
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
    
    Returns:
        polars.DataFrame: 按日期排序的所有日线数据
    """
    filters = []
    if start_date:
        filters.append((QfqStockDailyView.TRADE_DATE, ">=", start_date))
    if end_date:
        filters.append((QfqStockDailyView.TRADE_DATE, "<=", end_date))
    
    df = pl.from_arrow(
        database.select(
            model_cls=QfqStockDailyView,
            filters=filters if filters else None
        )
    )
    return df.lazy().sort(QfqStockDailyView.TRADE_DATE)


@st.cache_data(ttl=3600)
def get_index_daily(code, start_date, end_date) -> pl.DataFrame:
    """
    获取指数日线数据。
    
    Args:
        code: 指数代码
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        polars.DataFrame: 按日期排序的指数日线数据
    """
    df = pl.from_arrow(
        database.select(
            model_cls=IndexDaily,
            filters=[
                (IndexDaily.CODE, "=", code),
                (IndexDaily.TRADE_DATE, ">=", start_date),
                (IndexDaily.TRADE_DATE, "<=", end_date)
            ],
            )
        ).with_columns(
            cs.numeric().exclude(["trade_date", "code", "name"]).round(2)
        ).sort(IndexDaily.TRADE_DATE)

    return df

def truncate_all_tables(confirm=False):
    database.truncate_all_tables(confirm)

