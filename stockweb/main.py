"""
Streamlit Web 应用主入口
=========================

定义股票数据可视化系统的页面导航和全局配置。
"""

import streamlit as st
import sys
from pathlib import Path

# 添加项目路径到系统路径
sys.path.append(str(Path(__file__).parent.parent))

# 定义页面导航结构
pg = st.navigation({
    "主要功能": [
        st.Page("pages/home.py", title="首页", icon="🏠", default=True),
        st.Page("pages/kline_renderer.py", title="股票K线", icon="📈"),
        st.Page("pages/stock_selection.py", title="条件选股", icon="🔍"),
        st.Page("pages/horizontal_stats.py", title="横向统计", icon="📊"),
    ],
    "监控与支持": [
        st.Page("pages/market_monitor.py", title="市场预警", icon="🚨"),
        st.Page("pages/data_management.py", title="数据管理", icon="💾"),
        st.Page("pages/help.py", title="帮助文档", icon="📖"),
    ]
})

# 全局页面配置
st.set_page_config(page_title="股票数据可视化系统", layout="wide")

# 执行导航
pg.run()

# 公共页脚
st.divider()
st.caption("💡 数据仅供学习参考，不构成投资建议")