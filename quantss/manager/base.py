"""
管理器基类模块
==============

提供通用的懒加载管理器和动态代理实现，支持单例模式和线程池模式的资源管理。
"""

import threading
import time
from typing import Any, Dict, Generic, Literal, TypeVar

T = TypeVar("T")


class ThreadSlot:
    """
    线程槽类，包装实例及其活跃时间戳。
    
    用于线程池模式下追踪每个线程的连接实例及其使用时间，
    便于实现空闲连接的自动清理。
    """
    
    def __init__(self, instance: Any):
        """
        初始化线程槽。
        
        Args:
            instance: 被包装的实例对象
        """
        self.instance = instance
        self.last_used = time.time()

    def touch(self):
        """更新最后使用时间戳"""
        self.last_used = time.time()


class BaseLazyManager(Generic[T]):
    """
    支持全局单例与阻塞式线程池管理的通用基类。
    
    提供两种管理模式：
    - singleton: 全局共享一个实例
    - thread: 每个线程拥有独立实例，通过线程池限制最大并发数
    
    Args:
        auto_disconnect: 是否在上下文管理器退出时自动断开连接
        scope: 管理作用域，"singleton" 或 "thread"
        max_workers: 线程池模式下的最大连接数
        idle_timeout: 空闲连接超时时间（秒），超时后自动清理
        pool_timeout: 获取连接的超时时间（秒），None 表示无限等待
    """
    
    def __init__(
        self, 
        auto_disconnect: bool = True,
        scope: Literal["singleton", "thread"] = "singleton",
        max_workers: int = 16,
        idle_timeout: float = 300.0,
        pool_timeout: float | None = 30.0
    ):
        self.auto_disconnect = auto_disconnect
        self.scope = scope
        self.max_workers = max_workers
        self.idle_timeout = idle_timeout
        self.pool_timeout = pool_timeout
        
        # 使用条件变量支持阻塞等待和精准唤醒
        self._cv = threading.Condition()
        
        # 单例模式存储
        self._singleton_instance: T | None = None
        
        # 线程池模式存储 {thread_id: ThreadSlot}
        self._thread_pool: Dict[int, ThreadSlot] = {}

    def _build(self) -> T:
        """
        构建实例的抽象方法，子类必须实现。
        
        Returns:
            新构建的实例对象
        
        Raises:
            NotImplementedError: 子类未实现此方法时抛出
        """
        raise NotImplementedError

    def _initialize_hook(self, instance: T) -> None:
        """
        实例初始化钩子，在实例创建后、返回前调用。
        
        Args:
            instance: 刚创建的实例
        """
        pass

    def _cleanup_expired_threads_locked(self) -> bool:
        """
        清理过期或死亡线程的连接（调用时必须已持有锁）。
        
        检查所有线程槽，清理已死亡的线程或空闲超时的连接。
        
        Returns:
            是否成功释放了槽位
        """
        now = time.time()
        active_threads = {t.ident for t in threading.enumerate()}
        dead_or_expired_ids = []

        for tid, slot in self._thread_pool.items():
            if (tid not in active_threads) or (now - slot.last_used > self.idle_timeout):
                dead_or_expired_ids.append(tid)

        for tid in dead_or_expired_ids:
            slot = self._thread_pool.pop(tid, None)
            if slot and hasattr(slot.instance, "disconnect"):
                try:
                    slot.instance.disconnect()
                except Exception:
                    pass
        
        return len(dead_or_expired_ids) > 0

    def get_instance(self) -> T:
        """
        获取实例。
        
        根据配置的作用域返回单例实例或线程隔离实例。
        
        Returns:
            实例对象
        
        Raises:
            TimeoutError: 获取连接超时
        """
        if self.scope != "thread":
            # 单例模式
            if self._singleton_instance is None:
                with self._cv:
                    if self._singleton_instance is None:
                        instance = self._build()
                        if hasattr(instance, "connect"):
                            instance.connect()
                        self._initialize_hook(instance)
                        self._singleton_instance = instance
            return self._singleton_instance

        # 线程池模式
        current_tid = threading.get_ident()
        
        with self._cv:
            # 检查当前线程是否已持有连接
            if current_tid in self._thread_pool:
                slot = self._thread_pool[current_tid]
                slot.touch()
                return slot.instance

            start_time = time.time()
            
            # 阻塞循环：当池满且无法通过清理释放槽位时，挂起线程
            while len(self._thread_pool) >= self.max_workers:
                # 尝试清洗过期或死亡线程连接
                if self._cleanup_expired_threads_locked():
                    break  # 成功释放了至少一个槽位，跳出阻塞
                
                # 计算剩余等待时间（防止无限阻塞）
                remaining = None
                if self.pool_timeout is not None:
                    remaining = self.pool_timeout - (time.time() - start_time)
                    if remaining <= 0:
                        raise TimeoutError(f"获取连接超时：当前连接池已满（上限 {self.max_workers}）")
                
                # 挂起当前线程，等待其他线程释放连接时唤醒
                signaled = self._cv.wait(timeout=remaining)
                if not signaled and self.pool_timeout is not None:
                    raise TimeoutError(f"获取连接超时：当前连接池已满（上限 {self.max_workers}）")

            # 成功获取槽位，构建新物理连接
            try:
                instance = self._build()
                if hasattr(instance, "connect"):
                    instance.connect()
                self._initialize_hook(instance)
                
                self._thread_pool[current_tid] = ThreadSlot(instance)
                return instance
            except Exception:
                # 发生异常时，唤醒其他可能在等待的线程
                self._cv.notify()
                raise

    def release_instance(self) -> None:
        """
        释放当前线程持有的连接，并通知阻塞队列中的线程。
        
        仅在线程池模式下有效。
        """
        if self.scope != "thread":
            return
            
        current_tid = threading.get_ident()
        with self._cv:
            slot = self._thread_pool.pop(current_tid, None)
            if slot and hasattr(slot.instance, "disconnect"):
                try:
                    slot.instance.disconnect()
                except Exception:
                    pass
            # 通知并唤醒正在等待的下一个线程
            self._cv.notify()

    def close(self) -> None:
        """关闭所有连接并清理资源"""
        with self._cv:
            if self.scope == "thread":
                for slot in self._thread_pool.values():
                    if hasattr(slot.instance, "disconnect"):
                        try:
                            slot.instance.disconnect()
                        except Exception:
                            pass
                self._thread_pool.clear()
                self._cv.notify_all()
            else:
                if self._singleton_instance:
                    if hasattr(self._singleton_instance, "disconnect"):
                        self._singleton_instance.disconnect()
                    self._singleton_instance = None

    def __enter__(self) -> T:
        """上下文管理器进入方法"""
        return self.get_instance()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        上下文管理器退出方法。
        
        若 auto_disconnect 开启，自动释放当前线程的连接。
        """
        if self.auto_disconnect:
            self.release_instance()


class BaseDynamicProxy(Generic[T]):
    """
    通用懒加载动态代理类。
    
    延迟获取实例，仅在访问属性时才真正创建实例。
    """
    
    def __init__(self, manager: BaseLazyManager[T]):
        """
        初始化代理。
        
        Args:
            manager: 懒加载管理器实例
        """
        self.__dict__["_manager"] = manager

    def __getattr__(self, name: str) -> Any:
        """
        获取属性时延迟获取实例。
        
        Args:
            name: 属性名称
        
        Returns:
            实例的对应属性
        """
        return getattr(self._manager.get_instance(), name)

    def __repr__(self) -> str:
        """返回实例的字符串表示"""
        return repr(self._manager.get_instance())
