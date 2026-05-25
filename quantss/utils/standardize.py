"""
量化工具 - 标准化处理模块
============================
提供A股市场核心标准化能力：
1. 股票代码标准化（多格式转换、市场自动推断）
2. 交易日期标准化（多格式解析、合法性校验）
3. 金融产品类型判断（股票/ETF/指数）
4. 时区统一（上海时区东八区）

核心特性：
- 兼容多种输入格式，容错性强
- 严格遵循A股交易所官方编码规范
- 完整的异常处理机制
- 支持多格式输出切换
"""

import re

from datetime import datetime, date, timedelta, timezone
from typing import Optional, Union
from quantss.common import StockCodeFormat, TradeDateFormat
from quantss.common.enums import Exchange

# ========== 时区配置 ==========
SHANGHAI_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
"""datetime.timezone: 上海时区（东八区），统一A股时间处理的基准时区"""

# ========== 统一前缀规则配置（按产品类型和交易所分类） ==========
MARKET_PREFIXES = {
    "stock": {
        "SH": ("600", "601", "603", "605", "688", "689", "900",),
        "SZ": ("000", "001", "002", "003", "300", "301", "302", "200"),
        "BJ": ("920",),
    },
    "etf": {
        "SH": ("510", "511", "512", "513", "515", "516", "517", "518", "520", "526", "530", "551", "560", "561", "562", "563", "588", "589"),
        "SZ": ("159",),
        "BJ": (),
    },
    "index": {
        "SH": ("000", "880", "881", "999"),
        "SZ": ("399",),
        "BJ": ("899",),
    },
}
"""dict[str, dict[str, tuple]]: 按产品类型和交易所分类的代码前缀规则配置"""


def _normalize_code(
    code: Optional[Union[str, int]],
    target_format: Optional[StockCodeFormat],
    prefix_rules: dict[str, tuple]
) -> Union[str, dict]:
    """
    通用代码标准化函数（内部函数）

    Args:
        code: 输入代码（支持字符串/数字/None）
        target_format: 目标输出格式
        prefix_rules: 交易所前缀规则字典

    Returns:
        指定格式的字符串或包含所有格式的字典，失败时返回包含error的字典
    """
    VALID_MARKETS = {e.value for e in Exchange}
    
    try:
        if code is None:
            raise ValueError("Input code cannot be None")
        
        code = str(code).upper().strip()
        
        # 更宽容的正则：允许任意空白和多个点
        pattern = r"^\s*([A-Z]{2})?\s*\.?\s*(\d{5,6})\s*\.?\s*([A-Z]{2})?\s*$"
        match = re.match(pattern, code)
        
        if not match:
            raise ValueError(f"Invalid code format: {code}")
            
        prefix_market = match.group(1) or ""
        num_code = match.group(2)
        suffix_market = match.group(3) or ""
        
        # 市场推断与校验
        market = suffix_market or prefix_market
        if not market:
            if len(num_code) == 6:
                for mkt, prefixes in prefix_rules.items():
                    if num_code.startswith(prefixes):
                        market = mkt
                        break
        
        if market and market not in VALID_MARKETS:
            market = "UNKNOWN"
            
        # 构造结果
        result = {
            StockCodeFormat.PURE_CODE: num_code,
            StockCodeFormat.SUFFIX: f"{num_code}.{market}",
            StockCodeFormat.PREFIX_DOT: f"{market}.{num_code}",
            StockCodeFormat.PREFIX: f"{market}{num_code}"
        }
        
        # 根据参数返回
        if target_format:
            return result.get(target_format, result)
        return result
        
    except Exception as e:
        return {"error": str(e)}


def normalize_stock_code(
    code: Optional[Union[str, int]],
    target_format: StockCodeFormat = StockCodeFormat.PURE_CODE
) -> Union[str, dict]:
    """
    股票代码标准化处理：支持多格式输入，自动推断市场，输出指定格式代码

    支持的输入格式示例：
    - 纯数字: "600000"、"000001"
    - 后缀格式: "600000.SH"、"000001.SZ"
    - 前缀格式: "SH.600000"、"SZ000001"
    - 带空白/多分隔符: " SH . 600000 "、"000001 . SZ"

    自动推断规则：
    - 6位数字开头匹配对应交易所前缀则自动推断市场（SH/SZ/BJ）
    - 非6位数字或无匹配前缀则标记为UNKNOWN

    Args:
        code: 输入的股票代码（支持字符串/数字类型）
        target_format: 目标输出格式
            - PURE_CODE: 纯数字代码（如600000）
            - SUFFIX: 数字+后缀市场（如600000.SH）
            - PREFIX_DOT: 前缀市场+点+数字（如SH.600000）
            - PREFIX: 前缀市场+数字（如SH600000）
            默认值为 StockCodeFormat.PURE_CODE

    Returns:
        指定target_format时返回对应格式的字符串；未指定时返回包含所有格式的字典；
        处理失败时返回包含error键的字典

    Examples:
        >>> normalize_stock_code("600000")
        '600000'
        >>> normalize_stock_code("000001.SZ", StockCodeFormat.PREFIX_DOT)
        'SZ.000001'
        >>> normalize_stock_code("BJ920001", StockCodeFormat.SUFFIX)
        '920001.BJ'
        >>> normalize_stock_code("123456")  # 未知前缀
        {'pure_code': '123456', 'suffix': '123456.UNKNOWN', ...}
        >>> normalize_stock_code(None)
        {'error': 'Input code cannot be None'}
    """
    return _normalize_code(code, target_format, MARKET_PREFIXES["stock"])


def normalize_index_code(
    code: Optional[Union[str, int]],
    target_format: StockCodeFormat = StockCodeFormat.PURE_CODE
) -> Union[str, dict]:
    """
    指数代码标准化处理：支持多格式输入，自动推断市场，输出指定格式代码

    支持的输入格式示例：
    - 纯数字: "000001"（上证指数）、"399001"（深证成指）
    - 后缀格式: "000001.SH"、"399001.SZ"
    - 前缀格式: "SH.000001"、"SZ399001"

    自动推断规则：
    - 6位数字开头匹配对应交易所指数前缀则自动推断市场
    - 非6位数字或无匹配前缀则标记为UNKNOWN

    Args:
        code: 输入的指数代码（支持字符串/数字类型）
        target_format: 目标输出格式，默认值为 StockCodeFormat.PURE_CODE

    Returns:
        指定target_format时返回对应格式的字符串；未指定时返回包含所有格式的字典；
        处理失败时返回包含error键的字典

    Examples:
        >>> normalize_index_code("000001")
        '000001'
        >>> normalize_index_code("399001.SZ", StockCodeFormat.PREFIX_DOT)
        'SZ.399001'
    """
    return _normalize_code(code, target_format, MARKET_PREFIXES["index"])


def normalize_trade_date(
    input_date: Optional[Union[str, date, datetime]] = None,
    target_format: TradeDateFormat = TradeDateFormat.HYPHEN
) -> Union[str, date, datetime, dict]:
    """
    交易日期标准化处理：支持多格式输入，自动校验合法性，输出指定格式日期

    支持的输入类型/格式：
    - 日期对象: datetime.date(2020,1,1)、datetime.datetime(2020,1,1,12,34)
    - 纯数字字符串: "20200101"
    - 带分隔符字符串: "2020-01-01"、"2020/01/01"、"2020.01.01"、"2020-1-1"
    - 带时间字符串: "2020-01-01 12:34"、"2020/01/01 12:34:56"
    - None/空字符串: 自动使用当日日期（上海时区）

    日期合法性校验：
    - 自动检测非法日期（如2月30日、13月、32日等）
    - 自动补零（如1月→01月，9日→09日）

    Args:
        input_date: 输入的日期/时间
        target_format: 目标输出格式
            - PURE_NUM: 纯数字格式（20260101）
            - HYPHEN: 短横线分隔（2026-01-01）
            - SLASH: 斜杠分隔（2026/01/01）
            - DOT: 点分隔（2026.01.01）
            - CHINESE: 中文格式（2026年01月01日）
            - HYPHEN_DATETIME: 带时间的短横线格式（2026-01-01 12:34:56）
            - SLASH_DATETIME: 带时间的斜杠格式（2026/01/01 12:34:56）
            - CHINESE_DATETIME: 带时间的中文格式（2026年01月01日 12时34分56秒）
            默认值为 TradeDateFormat.HYPHEN

    Returns:
        指定target_format时返回对应格式的值；未指定时返回包含所有格式的字典；
        处理失败时返回包含error键的字典

    Examples:
        >>> normalize_trade_date("20200101")
        '2020-01-01'
        >>> normalize_trade_date(datetime(2020,1,1), TradeDateFormat.PURE_NUM)
        '20200101'
        >>> normalize_trade_date("2020-1-1 12:34", TradeDateFormat.CHINESE_DATETIME)
        '2020年01月01日 12时34分00秒'
        >>> normalize_trade_date("2020-02-30")  # 非法日期
        {'error': 'Date validation error: day is out of range for month'}
        >>> normalize_trade_date(None)  # 返回当日日期
        '2024-05-20'  # 示例值，实际为执行时的当日日期
    """
    try:
        # 1. 类型分流处理
        if isinstance(input_date, (datetime, date)):
            # 处理日期对象
            dt = input_date
            year, month, day = dt.year, dt.month, dt.day
            hour, minute, second = (dt.hour, dt.minute, dt.second) if isinstance(dt, datetime) else (0, 0, 0)
        
        else:
            # 处理字符串输入
            if input_date is None:
                input_date = get_today_date()
            
            date_str = str(input_date).strip()
            if not date_str:
                date_str = get_today_date()
            
            # 2. 正则匹配（支持多种分隔符和时间格式）
            pattern = r"^(\d{4})[-/.\s]?(\d{1,2})[-/.\s]?(\d{1,2})(?:\s+(\d{1,2}):?(\d{0,2}):?(\d{0,2}))?$"
            match = re.match(pattern, date_str)
            
            if not match:
                raise ValueError(f"Invalid date format: {date_str}")
            
            # 提取并转换数值
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            hour = int(match.group(4)) if match.group(4) else 0
            minute = int(match.group(5)) if match.group(5) else 0
            second = int(match.group(6)) if match.group(6) else 0
            
            # 3. 日期合法性校验（自动捕获2月30日、13月等错误）
            datetime(year, month, day, hour, minute, second)
        
        # 4. 构造全格式结果（自动补零）
        result = {
            # 基础日期格式
            TradeDateFormat.PURE_NUM: f"{year}{month:02d}{day:02d}",
            TradeDateFormat.HYPHEN: f"{year}-{month:02d}-{day:02d}",
            TradeDateFormat.SLASH: f"{year}/{month:02d}/{day:02d}",
            TradeDateFormat.DOT: f"{year}.{month:02d}.{day:02d}",
            TradeDateFormat.CHINESE: f"{year}年{month:02d}月{day:02d}日",
            
            # 带时间格式（默认补00:00:00）
            TradeDateFormat.HYPHEN_DATETIME: f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}",
            TradeDateFormat.SLASH_DATETIME: f"{year}/{month:02d}/{day:02d} {hour:02d}:{minute:02d}:{second:02d}",
            TradeDateFormat.CHINESE_DATETIME: f"{year}年{month:02d}月{day:02d}日 {hour:02d}时{minute:02d}分{second:02d}秒",

            # date datetime class
            TradeDateFormat.DATE_CLASS: date(year, month, day),
            TradeDateFormat.DATETIME_CLASS: datetime(year, month, day, hour, minute, second),
        }
        
        # 5. 按需求返回
        if target_format:
            return result.get(target_format, result)
        return result

    except ValueError as e:
        return {"error": f"Date validation error: {str(e)}"}
    except (TypeError, AttributeError) as e:
        return {"error": f"Type error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def _is_type(code: str, type_name: str) -> bool:
    """
    通用类型判断函数（内部函数）

    Args:
        code: 金融产品代码
        type_name: 产品类型名称（"stock"、"etf"、"index"）

    Returns:
        True表示匹配成功，False表示不匹配或代码格式错误
    """
    try:
        if type_name == "index":
            result = normalize_index_code(code, StockCodeFormat.SUFFIX)
        else:
            result = normalize_stock_code(code, StockCodeFormat.SUFFIX)
            
        if isinstance(result, dict) and "error" in result:
            return False
            
        stock_code_part, exchange = result.split(".")
        prefix_map = MARKET_PREFIXES.get(type_name, {})
        return stock_code_part.startswith(prefix_map.get(exchange, ()))
        
    except (ValueError, AttributeError):
        return False


def is_stock(code: str) -> bool:
    """
    判断输入代码是否为A股股票（不含ETF、指数）

    判定规则：
    1. 先标准化代码获取交易所和纯数字代码
    2. 根据交易所匹配对应股票前缀规则
    3. 匹配成功返回True，否则返回False

    Args:
        code: 股票代码（支持任意标准化兼容格式）

    Returns:
        True: 是A股股票；False: 不是A股股票（或代码格式错误）

    Examples:
        >>> is_stock("600000")
        True
        >>> is_stock("510050")  # ETF
        False
        >>> is_stock("000001.SZ")
        True
        >>> is_stock("000001")  # 上证指数
        False
        >>> is_stock("invalid_code")
        False
    """
    return _is_type(code, "stock")


def is_etf(code: str) -> bool:
    """
    判断输入代码是否为ETF产品

    判定规则：
    1. 先标准化代码获取交易所和纯数字代码
    2. 根据交易所匹配对应ETF前缀规则
    3. 匹配成功返回True，否则返回False

    Args:
        code: 金融产品代码（支持任意标准化兼容格式）

    Returns:
        True: 是ETF产品；False: 不是ETF产品（或代码格式错误）

    Examples:
        >>> is_etf("510050")
        True
        >>> is_etf("159919.SZ")
        True
        >>> is_etf("600000")  # 股票
        False
        >>> is_etf("000001")  # 指数
        False
        >>> is_etf("invalid_code")
        False
    """
    return _is_type(code, "etf")


def is_index(code: str) -> bool:
    """
    判断输入代码是否为指数

    判定规则：
    1. 先标准化代码获取交易所和纯数字代码
    2. 根据交易所匹配对应指数前缀规则
    3. 匹配成功返回True，否则返回False

    Args:
        code: 金融产品代码（支持任意标准化兼容格式）

    Returns:
        True: 是指数；False: 不是指数（或代码格式错误）

    Examples:
        >>> is_index("000001")  # 上证指数
        True
        >>> is_index("399001.SZ")  # 深证成指
        True
        >>> is_index("600000")  # 股票
        False
        >>> is_index("510050")  # ETF
        False
        >>> is_index("invalid_code")
        False
    """
    return _is_type(code, "index")


def get_today_date() -> str:
    """
    获取上海时区的当日日期（标准化为默认格式：HYPHEN）

    Returns:
        当日日期字符串（格式：YYYY-MM-DD）

    Examples:
        >>> get_today_date()  # 执行日期为2024-05-20时
        '2024-05-20'
    """
    return normalize_trade_date(datetime.now(SHANGHAI_TZ).date())


if __name__ == "__main__":
    """模块自测入口"""
    print("standardize test")

    try:
        print(normalize_stock_code("000001"))
        print(normalize_stock_code("000001", StockCodeFormat.PREFIX_DOT))

        print(normalize_trade_date("20100101"))
        print("date: ", normalize_trade_date("20100101", TradeDateFormat.DATE_CLASS))
        print("datetime: ", normalize_trade_date("20100101", TradeDateFormat.DATETIME_CLASS))
    except Exception as e:
        print(f"Test failed: {e}")


__all__ = [
    "normalize_trade_date",
    "normalize_stock_code",
    "normalize_index_code",
    "is_stock",
    "is_etf",
    "is_index",
    "get_today_date",
]
