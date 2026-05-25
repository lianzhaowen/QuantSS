"""
量化工具日志管理模块

该模块实现了全局唯一的单例日志类 QuantLogger，基于 loguru 封装，解决日志递归输出问题，
同时深度兼容 tqdm 进度条（避免控制台输出乱码），支持日志文件自动轮转、压缩和备份保留，
提供标准的日志级别接口（debug/info/warning/error/critical/exception/success），
保证多线程安全且兼顾生产环境性能。

核心特性：
- 单例模式：全局唯一实例，避免重复初始化日志配置
- tqdm 兼容：控制台输出适配 tqdm 进度条，无乱码/覆盖问题
- 多线程安全：开启 enqueue 机制保证多线程/多进程环境下日志安全
- 文件轮转：按大小自动轮转日志文件，支持压缩和备份数量限制
- 编码兼容：日志文件使用 UTF-8 编码，彻底解决中文乱码
- 性能优化：生产环境关闭诊断信息，提升日志输出性能
"""
import os

from loguru import logger as _logger
from tqdm import tqdm
from quantss.utils.app_paths import AppPaths

# 单例日志类：全局唯一，彻底解决递归问题
class QuantLogger:
    """
    单例日志类：全局唯一实例，彻底解决日志递归输出问题

    基于 loguru 封装，实现控制台+文件双端日志输出：
    - 控制台输出：适配 tqdm 进度条、带颜色标识、多线程安全
    - 文件输出：自动轮转、压缩备份、UTF-8 编码、异常栈追踪
    所有日志方法与 loguru 原生接口完全兼容，业务代码无需修改调用方式。
    """
    _instance = None  # 类级单例实例存储变量

    def __new__(cls, *args, **kwargs):
        """
        单例模式实现：创建并返回全局唯一的 QuantLogger 实例

        实现逻辑：
        1. 检查类级变量 _instance 是否已初始化
        2. 未初始化则调用父类 __new__ 创建实例，并执行 _setup 初始化配置
        3. 已初始化则直接返回现有实例，保证全局唯一

        Args:
            *args: 可变位置参数（预留扩展，无实际使用）
            **kwargs: 可变关键字参数（预留扩展，无实际使用）

        Returns:
            QuantLogger: 全局唯一的日志类实例
        """
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._setup()
        return cls._instance

    def _setup(self):
        """
        初始化日志配置（仅执行1次，首次创建实例时调用）

        初始化流程：
        1. 配置日志文件存储路径（基于 AppPaths 动态获取）
        2. 从项目配置读取日志级别、文件大小限制、备份数量
        3. 创建日志存储目录（若不存在则自动创建）
        4. 清空 loguru 默认处理器，避免重复输出
        5. 配置控制台输出处理器（tqdm 兼容、带颜色、多线程安全）
        6. 配置文件输出处理器（自动轮转、压缩、UTF-8 编码）

        配置说明：
        - enqueue=True: 多线程安全，日志异步入队
        - diagnose=False: 生产环境关闭诊断信息，提升性能
        - backtrace=True: 文件日志保留完整异常栈（便于问题排查）
        """
        # 路径配置
        self.LOG_DIR = AppPaths.log()  # 日志存储根目录
        self.LOG_PATH = os.path.join(self.LOG_DIR, "quantss.log")  # 主日志文件路径

        # 延迟导入 settings，避免循环导入
        from quantss.config import settings
        
        # 读取配置
        self.log_level = settings.log.LOG_LEVEL  # 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
        self.max_size = settings.log.LOG_MAX_SIZE  # 单日志文件最大大小（如 "100MB"）
        self.backup_count = settings.log.LOG_BACKUP_COUNT  # 保留的日志备份数量

        # 创建日志文件夹
        os.makedirs(self.LOG_DIR, exist_ok=True)

        # 清空默认处理器
        _logger.remove()

        # ===================== 核心：tqdm 兼容控制台输出（永不乱码）=====================
        _logger.add(
            lambda msg: tqdm.write(msg, end=""),
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
                "<level>{message}</level>"
            ),
            level=self.log_level,
            enqueue=True,       # 多线程安全（必须开）
            colorize=True,      # 保留颜色
            diagnose=False      # 生产环境关闭诊断，提升性能
        )

        # ===================== 文件输出（自动轮转、压缩）=====================
        _logger.add(
            sink=str(self.LOG_PATH),
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{name}:{function} | "
                "{message}"
            ),
            level=self.log_level,
            rotation=self.max_size,  # 达到指定大小自动轮转
            retention=self.backup_count,  # 保留指定数量的备份
            compression="zip",  # 压缩备份文件
            encoding="utf-8",  # UTF-8 编码避免中文乱码
            enqueue=True,  # 多线程安全
            backtrace=True,  # 保留完整异常栈
            diagnose=False  # 生产环境关闭诊断
        )

    # ==================== 对外日志接口（无递归、完全兼容原有代码）====================
    def debug(self, msg, *args, **kwargs):
        """
        输出 DEBUG 级别日志（调试信息，仅开发/测试环境使用）

        Args:
            msg (str): 日志消息模板字符串（支持格式化）
            *args: 消息模板的格式化参数（按位置匹配）
            **kwargs: 日志输出额外参数（参考 loguru.Logger.debug）

        Example:
            >>> logger.debug("调试信息：参数1={}, 参数2={}", 100, "test")
        """
        _logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """
        输出 INFO 级别日志（常规运行信息，生产环境默认开启）

        Args:
            msg (str): 日志消息模板字符串（支持格式化）
            *args: 消息模板的格式化参数（按位置匹配）
            **kwargs: 日志输出额外参数（参考 loguru.Logger.info）

        Example:
            >>> logger.info("量化任务启动成功，任务ID={}", task_id)
        """
        _logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """
        输出 WARNING 级别日志（警告信息，不影响程序运行但需关注）

        Args:
            msg (str): 日志消息模板字符串（支持格式化）
            *args: 消息模板的格式化参数（按位置匹配）
            **kwargs: 日志输出额外参数（参考 loguru.Logger.warning）

        Example:
            >>> logger.warning("数据源连接超时，将使用备用数据源")
        """
        _logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """
        输出 ERROR 级别日志（错误信息，功能异常但程序可继续运行）

        Args:
            msg (str): 日志消息模板字符串（支持格式化）
            *args: 消息模板的格式化参数（按位置匹配）
            **kwargs: 日志输出额外参数（参考 loguru.Logger.error）

        Example:
            >>> logger.error("策略执行失败，策略ID={}", strategy_id)
        """
        _logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        """
        输出 CRITICAL 级别日志（严重错误，程序可能无法继续运行）

        Args:
            msg (str): 日志消息模板字符串（支持格式化）
            *args: 消息模板的格式化参数（按位置匹配）
            **kwargs: 日志输出额外参数（参考 loguru.Logger.critical）

        Example:
            >>> logger.critical("数据库连接失败，程序即将退出")
        """
        _logger.critical(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        """
        输出异常日志（自动记录当前异常栈，ERROR 级别）

        注意：必须在 except 代码块中调用，否则无法捕获异常信息

        Args:
            msg (str): 日志消息模板字符串（支持格式化）
            *args: 消息模板的格式化参数（按位置匹配）
            **kwargs: 日志输出额外参数（参考 loguru.Logger.exception）

        Example:
            >>> try:
            ...     1 / 0
            ... except ZeroDivisionError:
            ...     logger.exception("计算出错，除数不能为0")
        """
        _logger.exception(msg, *args, **kwargs)

    def success(self, msg, *args, **kwargs):
        """
        输出 SUCCESS 级别日志（成功信息，绿色标识，本质为 INFO 级别）

        Args:
            msg (str): 日志消息模板字符串（支持格式化）
            *args: 消息模板的格式化参数（按位置匹配）
            **kwargs: 日志输出额外参数（参考 loguru.Logger.success）

        Example:
            >>> logger.success("量化回测完成，收益率={}%", 15.6)
        """
        _logger.success(msg, *args, **kwargs)

# ==================== 全局单例导出（延迟初始化，避免循环导入）====================

class LazyLogger:
    """
    延迟初始化的日志代理类
    
    通过 __getattr__ 实现延迟加载，只有在首次调用日志方法时才真正创建 QuantLogger 实例，
    彻底解决循环导入问题。
    """
    _instance = None
    
    def __getattr__(self, name):
        if self._instance is None:
            self._instance = QuantLogger()
        return getattr(self._instance, name)

logger = LazyLogger()
"""
全局唯一的日志实例（延迟初始化）

业务代码可直接导入该实例调用日志方法，无需重复创建实例，
完全兼容原有调用方式，无需修改业务代码。

Example:
    >>> from quantss.utils.logger import logger
    >>> logger.info("程序启动")
    >>> try:
    ...     run_strategy()
    ... except Exception as e:
    ...     logger.exception("策略执行失败")
"""

__all__ = ["logger"]