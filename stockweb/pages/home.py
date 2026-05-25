"""
首页模块
========

展示股票数据可视化系统的首页，包含功能介绍和数据统计看板。
"""

import streamlit as st

from stockweb.utils.data_utils import get_latest_data_date, get_total_kline_count, get_total_stock_count

# 页面标题
st.markdown("<div style='text-align: center; font-weight: bold; font-size:32px;'>📈 股票数据可视化系统</div>", unsafe_allow_html=True)
st.divider()

# 功能模块介绍
st.subheader("✨ 功能模块")
col1, col2 = st.columns(2)
with col1:
    st.success("📊 股票K线：K线图+技术指标分析")
    st.success("🔍 条件选股：批量筛选股票")
    st.success("💾 数据管理：导入/导出股票数据")
with col2:
    st.success("🚨 预警设定：股价实时监控")
    st.success("📖 帮助文档：使用教程")

# 数据看板
st.divider()
st.subheader("📊 数据看板")

latest_data_date = get_latest_data_date()
total_stock_count = get_total_stock_count()
total_kline_count = get_total_kline_count()

# 三列布局展示统计指标
stat_col1, stat_col2, stat_col3 = st.columns(3)
with stat_col1:
    st.metric(label="📅 最新数据日期", value=str(latest_data_date))
with stat_col2:
    st.metric(label="🏢 股票总数量", value=f"{total_stock_count:,} 只")
with stat_col3:
    st.metric(label="📈 K线总数据量", value=f"{total_kline_count:,} 条")
