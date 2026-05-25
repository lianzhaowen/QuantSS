"""
数据同步主入口模块
==================

提供全量数据同步的命令行入口，按顺序同步所有数据源。
"""

from quantss.utils.logger import logger
from quantss.services import (
    StockDailySyncService,
    CapitalDailySyncService,
    StockDividendSyncService,
    StockSyncService,
    TradeDateSyncService,
    IndexSyncService,
    IndexDailySyncService
)

def main():
    """
    执行全量数据同步。
    
    按顺序同步交易日历、股票列表、股票日线、每日股本、除权除息、指数列表和指数日线数据。
    """
    logger.info("=" * 70)
    logger.info(" 全量数据同步启动 | 严格顺序执行 ")
    logger.info("=" * 70)

    # ========== 1. 交易日日历（最先执行） ==========
    logger.info("📅 步骤 1/7：同步 交易日日历")
    TradeDateSyncService.sync_all()

    # ========== 2. 股票列表 ==========
    logger.info("📈 步骤 2/7：同步 股票列表")
    StockSyncService.sync_all()

    # ========== 3. 股票日线数据 ==========
    logger.info("📈 步骤 3/7：同步 股票日线数据")
    StockDailySyncService.sync_incremental()

    # ========== 4. 每日股本 ==========
    logger.info("📈 步骤 4/7：同步 股票每日股本")
    CapitalDailySyncService.sync_incremental()

    # ========== 5. 除权除息 ==========
    logger.info("📈 步骤 5/7：同步 股票除权除息")
    StockDividendSyncService.sync_incremental()

    # ========== 6. 指数列表 ==========
    logger.info("📈 步骤 6/7：同步 指数列表")
    IndexSyncService.sync_all()

    # ========== 7. 指数日线数据 ==========
    logger.info("📈 步骤 7/7：同步 指数日线数据")
    IndexDailySyncService.sync_incremental()

    # ========== 完成 ==========
    logger.info("✅✅✅ 全量同步 全部完成！")

if __name__ == "__main__":
    main()