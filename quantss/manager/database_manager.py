"""
数据库管理器模块
================

提供数据库连接的统一管理，支持 DuckDB 和 SQLite 两种数据库类型，
实现了单例模式和线程池模式的连接管理。
"""

import atexit
from typing import Literal
from quantss.common import DatabaseType
from quantss.config import settings
from quantss.database import BaseDatabase, DuckDBDatabase, SQLiteDatabase
from quantss.models import ALL_MODELS, QfqStockDailyView

from quantss.manager.base import BaseDynamicProxy, BaseLazyManager


class DatabaseManager(BaseLazyManager[BaseDatabase]):
    """
    数据库连接管理器。
    
    负责管理数据库连接的创建、复用和释放，支持单例模式和线程池模式。
    
    Args:
        db_type: 数据库类型，默认为配置文件中的值
        auto_disconnect: 是否自动断开连接（线程池模式下推荐设为 True）
        scope: 连接作用域，"singleton" 表示全局单例，"thread" 表示线程隔离
        max_workers: 线程池最大连接数
        idle_timeout: 连接空闲超时时间（秒）
        pool_timeout: 等待连接池的超时时间（秒），None 表示无限等待
    """
    
    def __init__(
        self, 
        db_type: str | None = None, 
        auto_disconnect: bool = True,
        scope: Literal["singleton", "thread"] = "singleton",
        max_workers: int = 8,
        idle_timeout: float = 60.0,
        pool_timeout: float | None = 15.0
    ):
        raw_type = db_type or settings.database.DATABASE_TYPE
        parsed_type = raw_type.value if hasattr(raw_type, "value") else str(raw_type)
        self.target_type = parsed_type.lower().strip()
        
        super().__init__(
            auto_disconnect=auto_disconnect, 
            scope=scope, 
            max_workers=max_workers, 
            idle_timeout=idle_timeout,
            pool_timeout=pool_timeout
        )

    def _build(self) -> BaseDatabase:
        """
        根据配置的数据库类型创建数据库实例。
        
        Returns:
            BaseDatabase: 数据库实例
        
        Raises:
            ValueError: 不支持的数据库类型
        """
        if self.target_type == DatabaseType.DUCKDB.value:
            return DuckDBDatabase(settings.database.DUCKDB_PATH)
        elif self.target_type == DatabaseType.SQLITE.value:
            return SQLiteDatabase(settings.database.SQLITE_PATH)
        raise ValueError(f"不支持的数据库类型: {self.target_type}")

    def _initialize_hook(self, instance: BaseDatabase) -> None:
        """
        数据库实例初始化钩子，创建所有模型对应的表。
        
        Args:
            instance: 数据库实例
        """
        instance.create_tables_from_models(ALL_MODELS)


# 全局数据库管理器实例（单例模式）
_db_manager = DatabaseManager(
    auto_disconnect=False,
    scope="singleton",
)

# 注册程序退出时自动关闭数据库连接
atexit.register(_db_manager.close)

# 数据库代理对象，对外暴露统一的数据库接口
database: BaseDatabase = BaseDynamicProxy[BaseDatabase](_db_manager)  # type: ignore

if __name__ == "__main__":
    import polars as pl
    from quantss.models import QfqStockDailyView, StockDaily, CapitalDaily, IndexDaily, StockDividend
    df = pl.DataFrame(database.select(QfqStockDailyView, [("code", "=", "601908"), ("trade_date", ">", "2022-05-06")])).sort("trade_date")
    # print(df)
    # database.delete(StockDaily, [("trade_date", "=", "2026-05-12")])
    # database.delete(CapitalDaily, [("trade_date", "=", "2026-05-12")])
    # database.delete(IndexDaily, [("trade_date", "=", "2026-05-12")])

    from quantss.utils import NMM, NMR, W_JX
    import polars.selectors as cs
    JXB, JXT = W_JX(pl.col("adj_open"), pl.col("adj_high"), pl.col("adj_low"), pl.col("adj_close"))
    df = df.with_columns(
        JXB=JXB,
        JXT=JXT,
    )

    print(df)