"""
市场监控页面模块
================

提供股价实时监控和预警功能。
"""

import streamlit as st
from utils.data_utils import get_current_price


# 页面标题
st.title("🚨 股价预警")

# 用户输入
ticker = st.text_input("股票代码", "AAPL")
target = st.number_input("预警价格", 180.0)

# 监控按钮
if st.button("启动监控"):
    price = get_current_price(ticker)
    if price:
        st.info(f"当前价：{price:.2f}")
        if price >= target:
            st.error("🚨 上涨预警触发！")