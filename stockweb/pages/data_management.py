"""
数据管理页面模块
================

提供数据同步和管理功能。
"""

import streamlit as st

from quantss.services import (
    StockDailySyncService,
    CapitalDailySyncService,
    StockDividendSyncService,
    StockSyncService,
    TradeDateSyncService,
    IndexSyncService,
    IndexDailySyncService
)

from stockweb.utils.data_utils import truncate_all_tables


# 会话状态初始化
if "task_running" not in st.session_state:
    st.session_state.task_running = False

if "task_step" not in st.session_state:
    st.session_state.task_step = 0

if "task_done" not in st.session_state:
    st.session_state.task_done = False

if "deleting" not in st.session_state:
    st.session_state.deleting = False

if "delete_done" not in st.session_state:
    st.session_state.delete_done = False

# 统一锁（关键修复）
if "busy" not in st.session_state:
    st.session_state.busy = False


# 页面标题
st.header("📊 数据管理中心")


# 全局锁状态同步（核心）
st.session_state.busy = (
    st.session_state.task_running or st.session_state.deleting
)


# 按钮区
col1, col2 = st.columns(2)

with col1:
    if st.button(
        "💾 全量同步（增量执行）",
        disabled=st.session_state.busy
    ):
        st.session_state.task_running = True
        st.session_state.task_step = 1
        st.session_state.task_done = False
        st.rerun()


with col2:
    if st.button(
        "🧹 清空数据库（危险）",
        disabled=st.session_state.busy
    ):
        st.session_state.deleting = True
        st.rerun()


# =========================================================
# 删除确认弹窗
# =========================================================
@st.dialog("⚠️ 数据清理确认")
def confirm_delete():
    st.warning("此操作不可恢复，会清空全部数据！")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("❌ 取消"):
            st.session_state.deleting = False
            st.rerun()

    with c2:
        if st.button("🧨 确认清空"):
            truncate_all_tables(True)

            # ⭐ 关键：必须释放 busy
            st.session_state.deleting = False
            st.session_state.delete_done = True
            st.rerun()


if st.session_state.deleting:
    confirm_delete()

if st.session_state.delete_done:
    st.success("✅ 数据库已清空完成")
    st.session_state.delete_done = False


# =========================================================
# 分割
# =========================================================
st.divider()


# =========================================================
# 进度区域
# =========================================================
step_placeholder = st.empty()
progress_bar = st.progress(0)
progress_text = st.empty()


def st_progress_callback(current, total, code):
    progress_bar.progress(current / total)
    progress_text.text(f"🔄 进度：{current}/{total}， 股票：{code}")


# =========================================================
# 同步任务
# =========================================================
def run_task():

    if not st.session_state.task_running:
        return

    step = st.session_state.task_step


    if step == 1:
        step_placeholder.info("📅 步骤 1/7：交易日历")
        TradeDateSyncService.sync_all()
        st.session_state.task_step = 2
        st.rerun()


    elif step == 2:
        step_placeholder.info("📈 步骤 2/7：股票列表")
        StockSyncService.sync_all()
        st.session_state.task_step = 3
        st.rerun()


    elif step == 3:
        step_placeholder.info("📊 步骤 3/7：股票日线")
        StockDailySyncService.sync_incremental(callback=st_progress_callback)
        st.session_state.task_step = 4
        st.rerun()


    elif step == 4:
        step_placeholder.info("💹 步骤 4/7：每日股本")
        CapitalDailySyncService.sync_incremental(callback=st_progress_callback)
        st.session_state.task_step = 5
        st.rerun()


    elif step == 5:
        step_placeholder.info("📉 步骤 5/7：除权除息")
        StockDividendSyncService.sync_incremental(callback=st_progress_callback)
        st.session_state.task_step = 6
        st.rerun()


    elif step == 6:
        step_placeholder.info("📈 步骤 6/7：指数列表")
        IndexSyncService.sync_all()
        st.session_state.task_step = 7
        st.rerun()


    elif step == 7:
        step_placeholder.info("📊 步骤 7/7：指数日线")
        IndexDailySyncService.sync_incremental(callback=st_progress_callback)
        st.session_state.task_step = 8
        st.rerun()


    else:
        st.session_state.task_running = False
        st.session_state.task_done = True

        step_placeholder.success("🎉 全量（增量）同步完成！")
        progress_bar.progress(1.0)
        progress_text.text("")


# =========================================================
# 执行入口
# =========================================================
if st.session_state.task_running:
    run_task()

elif st.session_state.task_done:
    st.success("🎉 上一次同步已完成")