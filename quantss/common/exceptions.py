"""
QuantSS 系统异常体系定义
========================
该模块定义了 QuantSS 系统中所有自定义异常的基类及各业务/功能模块的专属异常类，
统一异常结构（包含状态码和描述信息），便于异常捕获、处理和接口返回标准化。
"""

class BaseException(Exception):
    """
    QuantSS 系统所有自定义异常的基类
    继承自 Python 内置 Exception，扩展了状态码和标准化描述信息属性

    Attributes:
        message (str): 异常的详细描述信息，默认值为 "QuantSS 系统异常"
        code (int): 异常状态码，用于接口/脚本返回时的状态标识，默认值为 500
    """

    def __init__(self, message: str = "QuantSS 系统异常", code: int = 500):
        """
        初始化基类异常实例

        Args:
            message (str, optional): 异常描述信息，默认 "QuantSS 系统异常"
            code (int, optional): 异常状态码，默认 500
        """
        self.message = message  # 异常描述信息
        self.code = code       # 异常状态码（便于接口/脚本返回）
        super().__init__(self.message)

    def __str__(self) -> str:
        """
        重写字符串格式化方法，返回带状态码的异常信息

        Returns:
            str: 格式化后的异常字符串，格式为 "[状态码] 异常描述"
        """
        return f"[{self.code}] {self.message}"


class DataSourceException(BaseException):
    """
    数据来源相关异常类（如接口调用失败、爬虫获取数据失败、第三方数据源无响应等）
    继承自 BaseException，默认状态码 501，默认描述 "数据获取异常"
    """

    def __init__(self, message: str = "数据获取异常", code: int = 501):
        """
        初始化数据获取异常实例

        Args:
            message (str, optional): 数据获取异常的描述信息，默认 "数据获取异常"
            code (int, optional): 异常状态码，默认 501
        """
        super().__init__(message, code)


class DataProcessException(BaseException):
    """
    数据处理相关异常类（如数据清洗、转换、计算、聚合等逻辑执行失败）
    继承自 BaseException，默认状态码 502，默认描述 "数据处理异常"
    """

    def __init__(self, message: str = "数据处理异常", code: int = 502):
        """
        初始化数据处理异常实例

        Args:
            message (str, optional): 数据处理异常的描述信息，默认 "数据处理异常"
            code (int, optional): 异常状态码，默认 502
        """
        super().__init__(message, code)


class DataStorageException(BaseException):
    """
    数据存储/数据库相关异常类（如数据库连接失败、CRUD 操作失败、事务回滚等）
    继承自 BaseException，默认状态码 503，默认描述 "数据库操作异常"
    """

    def __init__(self, message: str = "数据库操作异常", code: int = 503):
        """
        初始化数据库操作异常实例

        Args:
            message (str, optional): 数据库操作异常的描述信息，默认 "数据库操作异常"
            code (int, optional): 异常状态码，默认 503
        """
        super().__init__(message, code)


class ConfigException(BaseException):
    """
    配置相关异常类（如配置文件缺失、配置项错误、配置解析失败、环境变量未配置等）
    继承自 BaseException，默认状态码 504，默认描述 "配置异常"
    """

    def __init__(self, message: str = "配置异常", code: int = 504):
        """
        初始化配置异常实例

        Args:
            message (str, optional): 配置异常的描述信息，默认 "配置异常"
            code (int, optional): 异常状态码，默认 504
        """
        super().__init__(message, code)


class DataValidationException(BaseException):
    """
    数据校验相关异常类（如入参校验失败、数据格式不合法、字段缺失、值域超出范围等）
    继承自 BaseException，默认状态码 505，默认描述 "数据校验失败"
    """

    def __init__(self, message: str = "数据校验失败", code: int = 505):
        """
        初始化数据校验异常实例

        Args:
            message (str, optional): 数据校验异常的描述信息，默认 "数据校验失败"
            code (int, optional): 异常状态码，默认 505
        """
        super().__init__(message, code)


class BusinessException(BaseException):
    """
    业务逻辑相关异常类（如业务规则校验失败、流程执行中断、权限不足等业务层面的失败）
    继承自 BaseException，默认状态码 506，默认描述 "业务处理失败"
    """

    def __init__(self, message: str = "业务处理失败", code: int = 506):
        """
        初始化业务处理异常实例

        Args:
            message (str, optional): 业务处理异常的描述信息，默认 "业务处理失败"
            code (int, optional): 异常状态码，默认 506
        """
        super().__init__(message, code)