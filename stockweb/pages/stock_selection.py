"""
条件选股页面模块
================

提供基于财务指标的股票筛选功能。
"""

import streamlit as st
import pandas as pd
import numpy as np

# 页面配置
st.set_page_config(page_title="条件选股工具", page_icon="🔍", layout="wide")
st.title("🔍 条件选股工具")
st.divider()


def get_all_stock_daily():
    """
    生成模拟股票历史数据。
    
    Returns:
        pandas.DataFrame: 包含多天交易日和核心选股指标的模拟数据
    """
    np.random.seed(42)
    stock_codes = [f"600{i:03d}" for i in range(1, 101)]
    stock_names = [f"股票{i}" for i in range(1, 101)]
    
    # 模拟最近 5 个交易日
    trade_dates = pd.date_range(end="2026-05-10", periods=5).strftime("%Y-%m-%d").tolist()
    
    all_data = []
    for date in trade_dates:
        data = {
            "trade_date": [date] * 100,
            "股票代码": stock_codes,
            "股票名称": stock_names,
            "市盈率(PE)": np.round(np.random.uniform(5, 50, 100), 2),
            "市净率(PB)": np.round(np.random.uniform(1, 10, 100), 2),
            "净利润增长率(%)": np.round(np.random.uniform(-10, 80, 100), 2),
            "营收增长率(%)": np.round(np.random.uniform(-5, 60, 100), 2),
            "总市值(亿元)": np.round(np.random.uniform(50, 2000, 100), 2)
        }
        all_data.append(pd.DataFrame(data))
        
    return pd.concat(all_data, ignore_index=True)


# 初始化/加载股票数据
if "stock_data" not in st.session_state:
    st.session_state.stock_data = get_all_stock_daily()

# 侧边栏：筛选条件设置
st.sidebar.header("📌 筛选条件")
st.sidebar.divider()

pe_min, pe_max = st.sidebar.slider("市盈率(PE)范围", 0.0, 60.0, (5.0, 30.0), 0.1)
pb_min, pb_max = st.sidebar.slider("市净率(PB)范围", 0.0, 15.0, (1.0, 8.0), 0.1)
profit_growth_min = st.sidebar.number_input("净利润增长率下限(%)", -20.0, 100.0, 10.0, 0.1)
revenue_growth_min = st.sidebar.number_input("营收增长率下限(%)", -10.0, 80.0, 5.0, 0.1)
market_cap_min, market_cap_max = st.sidebar.slider("总市值(亿元)范围", 0.0, 2500.0, (100.0, 1000.0), 1.0)

# 统计指标选择器
st.sidebar.subheader("📊 图表设置")
metrics = ["市盈率(PE)", "市净率(PB)", "净利润增长率(%)", "营收增长率(%)", "总市值(亿元)"]
selected_metric = st.sidebar.selectbox("选择统计指标", metrics)
agg_method = st.sidebar.selectbox("统计方式", ["平均值", "中位数", "最大值", "最小值"])

agg_dict = {"平均值": "mean", "中位数": "median", "最大值": "max", "最小值": "min"}

# ---------------------- 主界面：执行筛选 & 展示结果 ----------------------
# 基于侧边栏条件过滤全量数据
filtered_df = st.session_state.stock_data[
    (st.session_state.stock_data["市盈率(PE)"] >= pe_min) &
    (st.session_state.stock_data["市盈率(PE)"] <= pe_max) &
    (st.session_state.stock_data["市净率(PB)"] >= pb_min) &
    (st.session_state.stock_data["市净率(PB)"] <= pb_max) &
    (st.session_state.stock_data["净利润增长率(%)"] >= profit_growth_min) &
    (st.session_state.stock_data["营收增长率(%)"] >= revenue_growth_min) &
    (st.session_state.stock_data["总市值(亿元)"] >= market_cap_min) &
    (st.session_state.stock_data["总市值(亿元)"] <= market_cap_max)
]

st.subheader(f"📈 筛选股票的每日【{selected_metric}】{agg_method}走势")

if not filtered_df.empty:
    # 按交易日分组并计算统计值
    chart_data = (
        filtered_df.groupby("trade_date")[selected_metric]
        .agg(agg_dict[agg_method])
        .reset_index()
    )
    
    # 转换为适合 st.line_chart 的格式
    chart_data = chart_data.set_index("trade_date")
    
    # 绘制折线图
    st.line_chart(chart_data, width='stretch')
    
    # 辅助信息：显示当前日期下符合条件的代码数量
    count_data = filtered_df.groupby("trade_date")["股票代码"].count()
    st.caption(f"💡 注：各交易日满足筛选条件的股票数量在 {count_data.min()} ~ {count_data.max()} 只之间。")
else:
    st.warning("⚠️ 当前筛选条件下无匹配的股票数据，请放宽筛选条件。")
