"""
横向统计页面模块
================

提供指数走势分析和副图指标横向统计功能。
"""

import streamlit as st
import polars as pl

from datetime import datetime, timedelta
from pyecharts.charts import Kline, Line
from pyecharts import options as opts
from stockweb.utils.data_utils import  get_index_daily, get_all_stock_daily
from quantss.models import QfqStockDailyView
from quantss.utils.indicator import MA, W_JX, W_GL, W_TD, NMM, NMR


def analyze_stock_indicators_by_date(df):
    """按日期分组分析股票的指标状态"""
    
    if isinstance(df, pl.DataFrame) and len(df) > 0:
        OPEN = pl.col("adj_open")
        HIGH = pl.col("adj_high")
        LOW = pl.col("adj_low")
        CLOSE = pl.col("adj_close")

        jxb, jxt = W_JX(OPEN, HIGH, LOW, CLOSE)
        glb, glgb, glt, glgt = W_GL(CLOSE)
        tdb, tdt1, tdt2 = W_TD(OPEN, HIGH, LOW, CLOSE)
        _, nmmb, nmmt = NMM(CLOSE)
         
        sorted_df = df.sort(["code", QfqStockDailyView.TRADE_DATE])

        df_part1 = sorted_df.select([
            pl.col(QfqStockDailyView.TRADE_DATE), "adj_close",
            jxb.over("code").alias("JXB"), jxt.over("code").alias("JXT"),
            glb.over("code").alias("GLB"), glgb.over("code").alias("GLGB"),
            glt.over("code").alias("GLT"), glgt.over("code").alias("GLGT"), # 若已在 SQL 中计算则此处直接 pl.col("GLT") 即可
            tdb.over("code").alias("TDB"), tdt1.over("code").alias("TDT1"),
            tdt2.over("code").alias("TDT2"), nmmb.over("code").alias("NMMB"), nmmt.over("code").alias("NMMT"),
        ])

        optimized_grouped = (
            df_part1.group_by(QfqStockDailyView.TRADE_DATE)
            .agg([
                pl.when(pl.col("adj_close").is_not_null() & pl.col("adj_close").is_not_nan())
                .then(1).otherwise(0).sum().cast(pl.Int32).alias("total"),
                
                pl.col("JXB").sum().cast(pl.Int32), pl.col("JXT").sum().cast(pl.Int32),
                pl.col("GLB").sum().cast(pl.Int32), pl.col("GLGB").sum().cast(pl.Int32),
                pl.col("GLT").sum().cast(pl.Int32), pl.col("GLGT").sum().cast(pl.Int32),
                pl.col("TDB").sum().cast(pl.Int32), pl.col("TDT1").sum().cast(pl.Int32),
                pl.col("TDT2").sum().cast(pl.Int32), pl.col("NMMB").sum().cast(pl.Int32),
                pl.col("NMMT").sum().cast(pl.Int32),
            ])
            .sort(QfqStockDailyView.TRADE_DATE)
        )
        return optimized_grouped
    return pl.DataFrame()

def plot_combined_chart(index_df, index_name, daily_stats):
    """绘制合并图表：K线图在上，横向统计折线图在下，共用X轴"""
    from pyecharts.charts import Grid
    
    dates = [str(d).replace("-", "") for d in index_df["trade_date"].to_list()]
    kline_data = index_df.select(["open", "close", "low", "high"]).to_numpy().tolist()
    
    index_df = index_df.with_columns([
        MA(pl.col("close"), 60).round(2).alias("ma60"),
        MA(pl.col("close"), 250).round(2).alias("ma250")
    ])
    ma60_data = index_df["ma60"].to_list()
    ma250_data = index_df["ma250"].to_list()
    
    grid_left = "0.5%"
    grid_right = "2%"
    main_h = 500
    sub_h = 150
    sub_gap = 14
    sub_chart_count = 1
    total_height = main_h + sub_chart_count * (sub_h + sub_gap) + 80
    xaxis_indexes = list(range(sub_chart_count + 1))    

    kline = (
        Kline()
        .add_xaxis(xaxis_data=dates)
        .add_yaxis(
            series_name=f"{index_name}",
            y_axis=kline_data,
            itemstyle_opts=opts.ItemStyleOpts(
                color="#ef4444",
                color0="#22c55e",
                border_color="#ef4444",
                border_color0="#22c55e"
            )
        )
        .set_global_opts(
            # title_opts=opts.TitleOpts(title=f"{index_name} K线走势与指标横向统计", pos_top=10),
            datazoom_opts=[
                opts.DataZoomOpts(
                    type_="inside", 
                    xaxis_index=xaxis_indexes,
                    start_value=max(0, len(index_df) - 200), 
                    end_value=len(index_df) - 1,
                    range_mode="value",
                    ),
                opts.DataZoomOpts(
                    type_="slider",
                    xaxis_index=xaxis_indexes,
                    start_value=max(0, len(index_df) - 200), 
                    end_value=len(index_df) - 1,
                    range_mode="value",
                    ),
            ],
            xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(interval="auto")),
            yaxis_opts=opts.AxisOpts(
                position="right",
                is_scale=True,
                axislabel_opts=opts.LabelOpts(margin=2),
                splitline_opts=opts.SplitLineOpts(
                    is_show=True, linestyle_opts=opts.LineStyleOpts(color="#e0e0e0")
                )
            ),
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
            axispointer_opts=opts.AxisPointerOpts(
                is_show=True,
                link=[{"xAxisIndex": "all"}]
            ),
            legend_opts=opts.LegendOpts(
                is_show=True,
                type_="scroll",
                orient="horizontal",
                pos_left=grid_left,
                pos_right=grid_right,
                pos_top=40,
                item_gap=10
            ),
        )
    )
    
    line = (
        Line()
        .add_xaxis(xaxis_data=dates)
        .add_yaxis(series_name="MA60", y_axis=ma60_data, is_smooth=True, linestyle_opts=opts.LineStyleOpts(width=2, color="#3b82f6"), label_opts=opts.LabelOpts(is_show=False))
        .add_yaxis(series_name="MA250", y_axis=ma250_data, is_smooth=True, linestyle_opts=opts.LineStyleOpts(width=2, color="#f59e0b"), label_opts=opts.LabelOpts(is_show=False))
    )
    
    kline.overlap(line)
    
    top_px = main_h + 40 + 20
    stats_line = (
        Line()
        .add_xaxis(xaxis_data=dates)
        .add_yaxis(series_name="精细底", y_axis=daily_stats["JXB"].to_list(), is_smooth=False, linestyle_opts=opts.LineStyleOpts(width=2, color="#22c55e"), label_opts=opts.LabelOpts(is_show=False))
        .add_yaxis(series_name="精细顶", y_axis=daily_stats["JXT"].to_list(), is_smooth=False, linestyle_opts=opts.LineStyleOpts(width=2, color="#ef4444"), label_opts=opts.LabelOpts(is_show=False))
        .add_yaxis(series_name="海洋顶", y_axis=daily_stats["NMMT"].to_list(), is_smooth=False, linestyle_opts=opts.LineStyleOpts(width=2, color="#8b5cf6"), label_opts=opts.LabelOpts(is_show=False))
        .add_yaxis(series_name="海洋底", y_axis=daily_stats["NMMB"].to_list(), is_smooth=False, linestyle_opts=opts.LineStyleOpts(width=2, color="#06b6d4"), label_opts=opts.LabelOpts(is_show=False))
        .add_yaxis(series_name="通道顶", y_axis=daily_stats["TDT1"].to_list(), is_smooth=False, linestyle_opts=opts.LineStyleOpts(width=2, color="#f97316"), label_opts=opts.LabelOpts(is_show=False))
        .add_yaxis(series_name="通道底", y_axis=daily_stats["TDB"].to_list(), is_smooth=False, linestyle_opts=opts.LineStyleOpts(width=2, color="#3b82f6"), label_opts=opts.LabelOpts(is_show=False))
         .set_global_opts(
            xaxis_opts=opts.AxisOpts(is_show=False),
            yaxis_opts=opts.AxisOpts(position="right", axislabel_opts=opts.LabelOpts(margin=2)),
            legend_opts=opts.LegendOpts(
                is_show=True,
                type_="scroll",
                pos_left=grid_left,
                pos_right=grid_right,
                pos_top=f"{top_px + 4}px",
                item_gap=8
            ),
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
            axispointer_opts=opts.AxisPointerOpts(
                is_show=True,
                link=[{"xAxisIndex": "all"}]
            )
        )
    )
    
    grid = Grid(opts.InitOpts(width="100%", height=f"{total_height}px"))
    grid.add(
        kline,
        grid_opts=opts.GridOpts(
            pos_left=grid_left,
            pos_right=grid_right,
            pos_top="20px",
            height=f"{main_h}px",
            is_contain_label=False
        )
    )
    grid.add(stats_line, grid_opts=opts.GridOpts(pos_top=f"{top_px}px", height=f"{sub_h}px", pos_left=grid_left, pos_right=grid_right, is_contain_label=False))
    
    return grid.render_embed(), total_height


# 页面标题
st.title("📊 横向统计分析")

# 日期选择
default_end_date = datetime.now().strftime("%Y-%m-%d")
default_start_date = (datetime.now() - timedelta(days=360*5)).strftime("%Y-%m-%d")

col1, col2, col3 = st.columns(3)

# 指数选择
index_options = {
    "999999": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指",
    "000016": "上证50",
    "000300": "沪深300"
}
with col1:
    selected_index = st.selectbox("选择指数", list(index_options.keys()), format_func=lambda x: index_options[x])
with col2:
    start_date = st.date_input("开始日期", value=datetime.strptime(default_start_date, "%Y-%m-%d"))
with col3:
    end_date = st.date_input("结束日期", value=datetime.strptime(default_end_date, "%Y-%m-%d"))

start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")
# 获取指数数据和股票数据
index_df = None
stock_df = None

try:
    index_df = get_index_daily(selected_index, start_date_str, end_date_str)
except Exception as e:
    st.error(f"获取指数数据失败: {str(e)}")

try:
    stock_df = get_all_stock_daily(start_date_str, end_date_str)

    if isinstance(stock_df, pl.LazyFrame):
        stock_df = stock_df.collect()
    elif not isinstance(stock_df, pl.DataFrame):
        import pandas as pd
        if isinstance(stock_df, pd.DataFrame):
            stock_df = pl.from_pandas(stock_df)
        else:
            raise TypeError(f"Unknown data type: {type(stock_df)}")
    

except Exception as e:
    st.error(f"获取股票数据失败: {str(e)}")

# 绘制合并图表
if index_df is not None and len(index_df) > 0 and stock_df is not None and len(stock_df) > 0:
    cache_key = f"horizontal_stats_{start_date_str}_{end_date_str}"
    
    if st.session_state.get("cache_key") != cache_key or st.session_state.get("daily_stats") is None:
        with st.spinner("正在横向统计..."):
            daily_stats = analyze_stock_indicators_by_date(stock_df)
        st.session_state["daily_stats"] = daily_stats
        st.session_state["cache_key"] = cache_key
    else:
        daily_stats = st.session_state["daily_stats"]
    
    # 绘制合并图表
    if isinstance(daily_stats, pl.DataFrame) and not daily_stats.is_empty():
        html, chart_height = plot_combined_chart(index_df, index_options[selected_index], daily_stats)
        st.iframe(html, height=chart_height + 60)
        st.info(f"统计范围: {start_date_str} ~ {end_date_str}")
    else:
        st.warning("暂无横向统计数据")
else:
    if index_df is None or len(index_df) == 0:
        st.warning("暂无指数数据")
    if stock_df is None or len(stock_df) == 0:
        st.warning("暂无股票数据")