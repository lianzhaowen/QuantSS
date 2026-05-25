"""
数据源管理器模块
================

负责管理数据源的生命周期，支持单例和线程池模式。
"""

import atexit
from typing import Literal
from quantss.common.enums import DataSourceType
from quantss.config import settings
from quantss.datasource import BaseDataSource, TdxQuantDataSource
from quantss.manager.base import BaseDynamicProxy, BaseLazyManager


class DataSourceManager(BaseLazyManager[BaseDataSource]):
    """
    数据源专用的生命周期管理器。
    
    负责数据源的创建、复用和释放，支持单例模式和线程池模式。
    """
    
    def __init__(
        self, 
        ds_type: str | None = None, 
        auto_disconnect: bool = True,
        scope: Literal["singleton", "thread"] = "singleton",
        max_workers: int = 8,
        idle_timeout: float = 60.0,
        pool_timeout: float | None = 15.0
    ):
        # 参数清洗与解析完全内聚在子类中
        raw_type = ds_type or settings.datasource.DATASOURCE_TYPE
        parsed_type = raw_type.value if hasattr(raw_type, "value") else str(raw_type)
        self.target_type = parsed_type.lower().strip()
        
        super().__init__(
            auto_disconnect=auto_disconnect, 
            scope=scope, 
            max_workers=max_workers, 
            idle_timeout=idle_timeout,
            pool_timeout=pool_timeout
        )

    def _build(self) -> BaseDataSource:
        if self.target_type == DataSourceType.TDXQUANT:
            return TdxQuantDataSource()
        raise ValueError(f"不支持的数据源类型: {self.target_type}")


# 🌟 根据你的高并发策略进行实例化配置：
# 限制同时向物理行情源建立的最大并发连接为 8 个，满载时新线程阻塞等待最长 15 秒
_ds_manager = DataSourceManager(
    auto_disconnect=True,   # 配合多线程阻塞模式，用完即还
    scope="thread", 
    max_workers=settings.datasource.MAX_WORKERS,       
    pool_timeout=settings.datasource.POOL_TIMEOUT  
)

# _ds_manager = DataSourceManager(
#     auto_disconnect=True,
#     scope="singleton",
# )

# 注册程序退出时自动关闭连接
atexit.register(_ds_manager.close)

# 🏆 正式导出变量：显式附加类型提示，保障外部 IDE 代码提示完美补全
datasource: BaseDataSource = BaseDynamicProxy[BaseDataSource](_ds_manager)  # type: ignore

if __name__ == "__main__":
    """测试入口：验证多线程阻塞式数据源调度"""
    import concurrent.futures
    import time

    def worker_task(worker_id: int):
        # 使用上下文管理器，离开作用域自动释放连接
        with _ds_manager:
            print(f"[线程 {worker_id}] 已成功抢占并接入物理数据源...")
            # 模拟高频行情提取耗时
            time.sleep(2)
            # 通过全局代理对象透明调用底层方法
            # data = datasource.get_daily_kline("000001", start_date="2026-01-01")
            print(f"[线程 {worker_id}] 行情提取完毕，正在归还物理通道。")

    print("启动 12 个多线程任务抢占并发上限为 8 的数据源连接池...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(worker_task, i) for i in range(12)]
        concurrent.futures.wait(futures)
    print("所有多线程行情源调度测试完毕。")