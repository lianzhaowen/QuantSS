import os

"""
应用程序路径管理模块
负责统一管理QuantSS应用的各类核心目录（配置、日志、数据库）的路径，
并在初始化时自动创建所需目录，确保路径可用。
"""

class AppPaths:
    """
    应用路径管理类
    提供应用程序核心目录的路径获取方法，初始化时会自动创建所有必要目录。
    
    类属性:
        user_home: str | None
            用户主目录路径（如Linux的/home/user，Windows的C:\\Users\\user）
        approot: str | None
            应用根目录路径（用户主目录下的.qss文件夹）
        config_dir: str
            配置文件目录路径（approot下的config子文件夹）
        log_dir: str
            日志文件目录路径（approot下的log子文件夹）
        db_dir: str
            数据库文件目录路径（approot下的db子文件夹）
    """
    user_home = None
    approot = None

    @classmethod
    def _initialize(cls):
        """
        初始化类方法（内部调用）
        1. 解析用户主目录，构建应用各核心目录路径
        2. 自动创建应用根目录、配置目录、日志目录、数据库目录（若不存在）
        """
        # 初始化路径
        cls.user_home = os.path.expanduser("~")
        cls.approot = os.path.join(cls.user_home, ".qss")
        cls.config_dir = os.path.join(cls.approot, "config")
        cls.log_dir = os.path.join(cls.approot, "log")
        cls.db_dir = os.path.join(cls.approot, "db")
        
        # 批量创建目录（exist_ok=True避免目录已存在时报错）
        for dir_path in [cls.approot, cls.config_dir, cls.log_dir, cls.db_dir]:
            os.makedirs(dir_path, exist_ok=True)

    @classmethod
    def config(cls):
        """
        获取配置文件目录路径
        
        返回:
            str: 配置目录的绝对路径
        """
        return cls.config_dir

    @classmethod
    def log(cls):
        """
        获取日志文件目录路径
        
        返回:
            str: 日志目录的绝对路径
        """
        return cls.log_dir

    @classmethod
    def db(cls):
        """
        获取数据库文件目录路径
        
        返回:
            str: 数据库目录的绝对路径
        """
        return cls.db_dir
    
# 初始化路径（模块加载时自动执行）
AppPaths._initialize()