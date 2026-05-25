from functools import wraps
from inspect import signature

def retry(times: int = 3, delay: int = 1):
    """异常重试装饰器

    为函数添加异常自动重试功能，当函数执行抛出异常时，会按照指定次数和延迟重试，
    若所有重试均失败则最终抛出异常。

    Args:
        times: 重试总次数，默认3次
        delay: 每次重试的间隔时间（秒），默认1秒

    Returns:
        装饰器函数，用于包装目标函数

    Raises:
        Exception: 当重试次数耗尽后，抛出包含失败信息的异常

    Example:
        @retry(times=5, delay=2)
        def risky_function():
            # 可能抛出异常的业务逻辑
            pass
    """
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            for i in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    import time
                    time.sleep(delay)
            raise Exception(f"{func.__name__} 重试{times}次全部失败")
        return inner
    return wrapper

def auto_connect(func):
    """自动连接装饰器

    装饰类的实例方法，执行目标方法前会自动调用实例的 `connect()` 方法，
    适用于需要先建立连接（如数据库、接口连接）再执行业务逻辑的场景。

    Args:
        func: 被装饰的类实例方法

    Returns:
        包装后的方法

    Notes:
        被装饰方法所属的类必须实现 `connect()` 方法，否则会抛出AttributeError

    Example:
        class DBHandler:
            def connect(self):
                # 建立数据库连接
                pass

            @auto_connect
            def query_data(self, sql):
                # 执行查询（执行前会自动调用connect）
                pass
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        self.connect()  # 自动执行连接逻辑
        return func(self, *args, **kwargs)
    return wrapper


def param_standard_wrap():
    """参数标准化装饰器工厂

    装饰类的实例方法，自动标准化方法入参：
    1. 处理 `code` 参数：调用实例的 `_adapt_code()` 方法适配编码格式
    2. 处理日期类参数：调用实例的 `_adapt_date()` 方法适配日期格式，
       支持的日期参数名包括：start_date、end_date、date、report_date

    Returns:
        装饰器函数，用于包装目标方法

    Notes:
        1. 被装饰方法所属的类必须实现 `_adapt_code()` 和 `_adapt_date()` 方法
        2. 会自动处理参数默认值，确保标准化逻辑覆盖所有入参
        3. 移除 `self` 参数后再处理，避免干扰实例自身的属性

    Example:
        class DataProcessor:
            def _adapt_code(self, code):
                # 统一编码格式，如将股票代码补全为6位
                return f"{code:06d}"

            def _adapt_date(self, date):
                # 统一日期格式为YYYY-MM-DD
                return date.strftime("%Y-%m-%d")

            @param_standard_wrap()
            def get_data(self, code, start_date, end_date=None):
                # 入参已被自动标准化
                pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # 获取完整参数（包含默认值）
            sig = signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()
            all_args = bound_args.arguments

            # 移除 self，不处理实例自身
            all_args.pop("self", None)

            # 适配code参数格式
            if "code" in all_args and all_args["code"] is not None:
                all_args["code"] = self._convert_stock_code(all_args["code"])

            # 适配日期类参数格式
            date_keys = ["start_date", "end_date", "date", "report_date"]
            for key in date_keys:
                if key in all_args and all_args[key] is not None:
                    all_args[key] = self._convert_trade_date(all_args[key])

            # 统一用 **解包，彻底避免重复传参
            return func(self, **all_args)
        return wrapper
    return decorator