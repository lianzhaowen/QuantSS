"""
K线图页面模块
=============

提供股票K线图展示和技术指标分析功能。
"""

import streamlit as st
import polars as pl

import polars.selectors as cs
from pyecharts import options as opts
from pyecharts.charts import Kline, Line, Bar, Grid
from pyecharts.commons.utils import JsCode
from datetime import datetime, timedelta
from quantss.common.constants import CHINA_SECURITY_MARKET_ESTABLISH_DATE
from quantss.models import Stock
from quantss.utils import BIAS
from quantss.utils.indicator import CCI, KDJ, MA, MACD, RSI, W_JX, W_GL, W_TD
from stockweb.utils.data_utils import get_stock_daily, get_stock_list


# 页面配置
st.set_page_config(page_title="K线图", layout="wide")

st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-left: 2rem;
    padding-right: 2rem;
    padding-bottom: 0rem;
    max-width: 100%;
}
</style>
""", unsafe_allow_html=True)


# 会话状态缓存初始化
if "kline_df" not in st.session_state:
    st.session_state.kline_df = None
if "current_ticker" not in st.session_state:
    st.session_state.current_ticker = ""
if "cache_key" not in st.session_state:
    st.session_state.cache_key = None


# ===================== 侧边栏 =====================
with st.sidebar:
    st.markdown("##### 📊 查询参数")

    stock_df = get_stock_list()
    stock_options = (
        stock_df.select(pl.concat_str([pl.col(Stock.CODE), pl.col(Stock.NAME)], separator=" - "))
        .to_series()
        .to_list()
    )

    selected_stock = st.selectbox("股票代码", stock_options)
    ticker = selected_stock.split("-")[0].strip()

    c1, c2 = st.columns(2)
    start_date = c1.date_input(
        "开始",
        datetime.now() - timedelta(days=365 * 5),
        min_value=CHINA_SECURITY_MARKET_ESTABLISH_DATE
    )
    end_date = c2.date_input(
        "结束",
        datetime.now(),
        min_value=CHINA_SECURITY_MARKET_ESTABLISH_DATE
    )

    ma_options = ["MA5", "MA10", "MA20", "MA30", "MA60", "MA120", "MA250"]
    default_ma_option = ["MA60", "MA120", "MA250"]
    selected_ma = st.multiselect("主图均线", options=ma_options, default=default_ma_option)

    sub_indicator_options = ["VOL 成交量", "MACD 指标", "RSI 指标", "KDJ 指标", "CCI 指标", "BIAS 指标"]
    default_indicator_option = ["VOL 成交量", "MACD 指标"]
    selected_sub_indicators = st.multiselect("副图指标", options=sub_indicator_options, default=default_indicator_option)

    show_vol = "VOL 成交量" in selected_sub_indicators
    show_macd = "MACD 指标" in selected_sub_indicators
    show_rsi = "RSI 指标" in selected_sub_indicators
    show_kdj = "KDJ 指标" in selected_sub_indicators
    show_cci = "CCI 指标" in selected_sub_indicators
    show_bias = "BIAS 指标" in selected_sub_indicators

cache_key = f"{ticker}-{start_date}-{end_date}"

if st.session_state.cache_key != cache_key:
    with st.spinner("加载数据..."):
        df = get_stock_daily(ticker, str(start_date), str(end_date))

        if df is not None and df.height > 0:
            df = df.sort("trade_date")

            st.session_state.kline_df = df
            st.session_state.current_ticker = selected_stock
            st.session_state.cache_key = cache_key
        else:
            st.session_state.kline_df = None
            st.warning("未获取到数据")

col1, col2 = st.columns([3, 1])
with col1:
    st.subheader("📊 股票 K 线分析 等比前复权")
with col2:
    st.subheader(st.session_state.current_ticker)

# ===================== 绘图 =====================
def render_chart(df):
    df = df.drop_nulls(subset=["open", "close", "high", "low"])
    dates = df["trade_date"].to_list()
    k_values = (
        df.select(["adj_open", "adj_close", "adj_low", "adj_high", "pct_chg", "adj_volume", "adj_amount"])
        .to_numpy()
        .tolist()
    )
    opens = df["adj_open"].to_list()
    closes = df["adj_close"].to_list()
    volumes = df["adj_volume"].to_list() 
    sub_chart_count = sum([show_vol, show_macd, show_rsi, show_kdj, show_cci, show_bias])
    xaxis_indexes = list(range(sub_chart_count + 1))

    rise_color = "#ff4b4b"
    fall_color = "#26a69a"
    grid_left = "0.5%"
    grid_right = "2%"

    # ---------------- 主图 K线 ----------------
    kline = (
        Kline(opts.InitOpts(width="100%", height="500px"))
        .add_xaxis(dates)
        .add_yaxis(
            "OHLC", k_values,
            itemstyle_opts=opts.ItemStyleOpts(
                color=rise_color,
                color0=fall_color,
                border_color=rise_color,
                border_color0=fall_color
            ),
        )
        .set_global_opts(
            datazoom_opts=[
                opts.DataZoomOpts(
                    type_="inside", 
                    xaxis_index=xaxis_indexes,
                    start_value=max(0, len(df) - 200), 
                    end_value=len(df) - 1,
                    range_mode="value",
                    ),
                opts.DataZoomOpts(
                    type_="slider",
                    xaxis_index=xaxis_indexes,
                    start_value=max(0, len(df) - 200), 
                    end_value=len(df) - 1,
                    range_mode="value",
                    ),
            ],
            yaxis_opts=opts.AxisOpts(
                position="right",
                is_scale=True,
                axislabel_opts=opts.LabelOpts(margin=2),
                splitline_opts=opts.SplitLineOpts(
                    is_show=True, linestyle_opts=opts.LineStyleOpts(color="#e0e0e0")
                )
            ),
            xaxis_opts=opts.AxisOpts(
                axislabel_opts=opts.LabelOpts(interval="auto"),
                axistick_opts=opts.AxisTickOpts(is_show=False)
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="cross",
                formatter=JsCode(
                    """
                    function(params) {
                        if (!params || !params.length) {
                            return '';
                        }
                        var lines = [params[0].axisValue];
                        for (var i = 0; i < params.length; i++) {
                            var p = params[i];
                            var val = p.data;
                            var marker = p.marker || '';
                            if (Array.isArray(val) && val.length >= 4) {
                                lines.push(marker + '开盘价: ' + val[1]);
                                lines.push(marker + '收盘价: ' + val[2]);
                                lines.push(marker + '最低价: ' + val[3]);
                                lines.push(marker + '最高价: ' + val[4]);
                                lines.push(marker + '涨幅: ' + val[5] + ' %');
                                lines.push(marker + '成交量: ' + val[6] + ' 万股');
                                lines.push(marker + '成交额: ' + val[7] + ' 亿元');
                            } else {
                                if (Array.isArray(val)) {
                                    val = val.length ? val[val.length - 1] : '-';
                                }
                                if (val && typeof val === 'object' && val.value !== undefined) {
                                    val = val.value;
                                }
                                lines.push(marker + p.seriesName + ': ' + val);
                            }
                        }
                        return lines.join('<br/>');
                    }
                    """
                )
            ),
            axispointer_opts=opts.AxisPointerOpts(
                is_show=True
            ),
            legend_opts=opts.LegendOpts(
                is_show=True,
                type_="scroll",
                orient="horizontal",
                pos_left=grid_left,
                pos_right=grid_right,
                pos_top=20,
                item_gap=10,
                item_width=14,
                item_height=8
            ),
        )
    )

    # 主图均线
    ma_line = Line().add_xaxis(dates).set_global_opts(xaxis_opts=opts.AxisOpts(is_show=False))
    colors = ["#FF9900", "#3366CC", "#9900CC", "#CC0066", "#009966", "#FF3333", "#3399FF"]
    # 按 ma_options 顺序排列
    selected_ma_sorted = [ma for ma in ma_options if ma in selected_ma]

    for i, ma in enumerate(selected_ma_sorted):
        if ma in df.columns:
            ma_line.add_yaxis(
                ma, 
                df[ma].to_list(), 
                linestyle_opts=opts.LineStyleOpts(width=1.4, color=colors[i % len(colors)]),
                label_opts=opts.LabelOpts(is_show=False)
            )
    kline.overlap(ma_line)

    # 布局
    cnt = sub_chart_count
    main_h = 500
    sub_h = 150
    sub_gap = 14
    total_height = main_h + cnt * (sub_h + sub_gap) + 80
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

    top_px = main_h + 40 + 20
    row_h = sub_h

    # 成交量
    if show_vol:
        vol_items = [
            opts.BarItem(
                name=dates[i],
                value=volumes[i],
                itemstyle_opts=opts.ItemStyleOpts(
                    color=rise_color if closes[i] >= opens[i] else fall_color
                ),
            )
            for i in range(len(volumes))
        ]
        bar = (
            Bar()
            .add_xaxis(dates)
            .add_yaxis(
                "VOL",
                vol_items,
                label_opts=opts.LabelOpts(is_show=False),
            )
            .set_global_opts(
                xaxis_opts=opts.AxisOpts(is_show=False),
                yaxis_opts=opts.AxisOpts(position="right", axislabel_opts=opts.LabelOpts(margin=2)),
                legend_opts=opts.LegendOpts(
                    is_show=True,
                    type_="scroll",
                    pos_left=grid_left,
                    pos_right=grid_right,
                    pos_top=f"{top_px + 4}px",
                    item_gap=8,
                    item_width=12,
                    item_height=8
                ),
                tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
                axispointer_opts=opts.AxisPointerOpts(is_show=True),
            )
        )
        vol_lines = (
            Line()
            .add_xaxis(dates)
            .add_yaxis(
                series_name="VOL5",
                y_axis=df["VOL5"].to_list(), 
                # is_symbol_show=False,
                # is_smooth=True,
                linestyle_opts=opts.LineStyleOpts(width=1.4, color="#8FBC8F"), 
                label_opts=opts.LabelOpts(is_show=False),
            )
            .add_yaxis(
                series_name="VOL34",
                y_axis=df["VOL34"].to_list(),  
                # is_symbol_show=False,
                # is_smooth=True,
                linestyle_opts=opts.LineStyleOpts(width=1.4, color="#FF1493"),
                label_opts=opts.LabelOpts(is_show=False),
            )
            .add_yaxis(
                series_name="成交额",
                y_axis=df["adj_amount"].to_list(), 
                is_symbol_show=False,       
                linestyle_opts=opts.LineStyleOpts(width=0, opacity=0), 
                label_opts=opts.LabelOpts(is_show=False),
            )
        )
        bar.overlap(vol_lines)
        grid.add(bar, grid_opts=opts.GridOpts(pos_top=f"{top_px}px", height=f"{row_h}px", pos_left=grid_left, pos_right=grid_right, is_contain_label=False))
        top_px += row_h + sub_gap

    # MACD
    if show_macd:
        macd_values = df["MACD"].to_list()
        macd_bar_items = [
            opts.BarItem(
                name=dates[i],
                value=macd_values[i],
                itemstyle_opts=opts.ItemStyleOpts(
                    color=rise_color if macd_values[i] >= 0 else fall_color
                ),
            )
            for i in range(len(macd_values))
        ]
        macd_bar = (
            Bar()
            .add_xaxis(dates)
            .add_yaxis("MACD", macd_bar_items, label_opts=opts.LabelOpts(is_show=False))
        )
        l = (
            Line()
            .add_xaxis(dates)
            .add_yaxis("DIF", df["DIF"].to_list(), label_opts=opts.LabelOpts(is_show=False))
            .add_yaxis("DEA", df["DEA"].to_list(), label_opts=opts.LabelOpts(is_show=False))
            .set_global_opts(
                xaxis_opts=opts.AxisOpts(is_show=False),
                yaxis_opts=opts.AxisOpts(position="right", axislabel_opts=opts.LabelOpts(margin=2)),
                legend_opts=opts.LegendOpts(
                    is_show=True,
                    type_="scroll",
                    pos_left=grid_left,
                    pos_right=grid_right,
                    pos_top=f"{top_px + 4}px",
                    item_gap=8,
                    item_width=12,
                    item_height=8
                ),
                tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
                axispointer_opts=opts.AxisPointerOpts(is_show=True),
            )
        )
        l.overlap(macd_bar)
        grid.add(l, grid_opts=opts.GridOpts(pos_top=f"{top_px}px", height=f"{row_h}px", pos_left=grid_left, pos_right=grid_right, is_contain_label=False))
        top_px += row_h + sub_gap

    # RSI
    if show_rsi:
        l = (
            Line()
            .add_xaxis(dates)
            .add_yaxis("RSI", df["RSI"].to_list(), label_opts=opts.LabelOpts(is_show=False))
            .set_global_opts(
                xaxis_opts=opts.AxisOpts(is_show=False),
                yaxis_opts=opts.AxisOpts(position="right", axislabel_opts=opts.LabelOpts(margin=2)),
                legend_opts=opts.LegendOpts(
                    is_show=True,
                    type_="scroll",
                    pos_left=grid_left,
                    pos_right=grid_right,
                    pos_top=f"{top_px + 4}px",
                    item_gap=8,
                    item_width=12,
                    item_height=8
                ),
                tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
                axispointer_opts=opts.AxisPointerOpts(is_show=True),
            )
        )
        grid.add(l, grid_opts=opts.GridOpts(pos_top=f"{top_px}px", height=f"{row_h}px", pos_left=grid_left, pos_right=grid_right, is_contain_label=False))
        top_px += row_h + sub_gap

    # KDJ
    if show_kdj:
        l = (
            Line()
            .add_xaxis(dates)
            .add_yaxis("K", df["K"].to_list(), label_opts=opts.LabelOpts(is_show=False))
            .add_yaxis("D", df["D"].to_list(), label_opts=opts.LabelOpts(is_show=False))
            .add_yaxis("J", df["J"].to_list(), label_opts=opts.LabelOpts(is_show=False))
            .set_global_opts(
                xaxis_opts=opts.AxisOpts(is_show=False),
                yaxis_opts=opts.AxisOpts(position="right", axislabel_opts=opts.LabelOpts(margin=2)),
                legend_opts=opts.LegendOpts(
                    is_show=True,
                    type_="scroll",
                    pos_left=grid_left,
                    pos_right=grid_right,
                    pos_top=f"{top_px + 4}px",
                    item_gap=8,
                    item_width=12,
                    item_height=8
                ),
                tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
                axispointer_opts=opts.AxisPointerOpts(is_show=True),
            )
        )
        grid.add(l, grid_opts=opts.GridOpts(pos_top=f"{top_px}px", height=f"{row_h}px", pos_left=grid_left, pos_right=grid_right, is_contain_label=False))
        top_px += row_h + sub_gap

    # CCI
    if show_cci:
        l = (
            Line()
            .add_xaxis(dates)
            .add_yaxis("CCI", df["CCI"].to_list(), label_opts=opts.LabelOpts(is_show=False))
            .set_global_opts(
                xaxis_opts=opts.AxisOpts(is_show=False),
                yaxis_opts=opts.AxisOpts(position="right", axislabel_opts=opts.LabelOpts(margin=2)),
                legend_opts=opts.LegendOpts(
                    is_show=True,
                    type_="scroll",
                    pos_left=grid_left,
                    pos_right=grid_right,
                    pos_top=f"{top_px + 4}px",
                    item_gap=8,
                    item_width=12,
                    item_height=8
                ),
                tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
                axispointer_opts=opts.AxisPointerOpts(is_show=True),
            )
        )
        grid.add(l, grid_opts=opts.GridOpts(pos_top=f"{top_px}px", height=f"{row_h}px", pos_left=grid_left, pos_right=grid_right, is_contain_label=False))
        top_px += row_h + sub_gap

    # BIAS
    if show_bias:
        l = (
            Line()
            .add_xaxis(dates)
            .add_yaxis("BIAS60", df["BIAS60"].to_list(), label_opts=opts.LabelOpts(is_show=False))
            .add_yaxis("BIAS120", df["BIAS120"].to_list(), label_opts=opts.LabelOpts(is_show=False))
            .add_yaxis("BIAS250", df["BIAS250"].to_list(), label_opts=opts.LabelOpts(is_show=False))
            .set_global_opts(
                xaxis_opts=opts.AxisOpts(is_show=False),
                yaxis_opts=opts.AxisOpts(position="right", axislabel_opts=opts.LabelOpts(margin=2)),
                legend_opts=opts.LegendOpts(
                    is_show=True,
                    type_="scroll",
                    pos_left=grid_left,
                    pos_right=grid_right,
                    pos_top=f"{top_px + 4}px",
                    item_gap=8,
                    item_width=12,
                    item_height=8
                ),
                tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
                axispointer_opts=opts.AxisPointerOpts(is_show=True),
            )
        )
        grid.add(l, grid_opts=opts.GridOpts(pos_top=f"{top_px}px", height=f"{row_h}px", pos_left=grid_left, pos_right=grid_right, is_contain_label=False))

    return grid.render_embed(), total_height

# ===================== 主界面 =====================
if st.session_state.kline_df is not None:
    html, chart_height = render_chart(st.session_state.kline_df)
    st.iframe(html, height=chart_height + 60)
else:
    st.info("👈 请先查询数据")