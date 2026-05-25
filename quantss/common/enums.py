"""
量化业务通用枚举类模块
========================
该模块定义了A股量化场景下的核心枚举类型，覆盖交易所、K线周期、复权类型、代码/日期格式、数据源/存储等维度，
所有枚举值均与下游行情接口（如tdxquant）、数据存储规范严格对齐，确保业务逻辑的一致性和可维护性。

核心设计原则：
1. 枚举值均为字符串类型（继承str, Enum），便于接口传参和序列化
2. 每个枚举类附带详细使用场景说明，降低跨模块理解成本
3. 枚举命名与业务语义强关联，避免魔法值硬编码
"""

from enum import Enum

class Exchange(str, Enum):
    """
    证券交易所枚举（适配A股市场三大交易所）

    核心使用场景：
    - 标的代码解析（如60XXXX对应SH、00XXXX对应SZ）
    - 行情接口请求时指定交易所维度
    - 数据存储时按交易所分类

    枚举值说明：
    """
    SZ = "SZ"  # 深圳证券交易所（包含创业板、中小板等板块）
    SH = "SH"  # 上海证券交易所（包含主板、科创板等板块）
    BJ = "BJ"  # 北京证券交易所（北交所，服务创新型中小企业）

class KlinePeriod(str, Enum):
    """
    K线周期枚举（对应tdxquant行情接口的period参数）

    枚举值与tdxquant行情接口的period参数1:1对齐，确保接口调用参数一致性。

    核心使用场景：
    - 调用行情接口获取指定粒度的K线数据
    - K线数据存储时的周期维度标识
    - 技术分析时的周期切换（如日线级别趋势分析、分钟线级别择时）

    枚举值说明（对应行情接口参数）：
    """
    MINUTE_1 = "1m"     # 1分钟K线（高频交易/日内择时场景）
    MINUTE_5 = "5m"     # 5分钟K线（短期趋势判断）
    MINUTE_15 = "15m"   # 15分钟K线（日内波段分析）
    MINUTE_30 = "30m"   # 30分钟K线（半日趋势分析）
    MINUTE_60 = "1h"    # 60分钟（1小时）K线（日内趋势核心周期）
    DAY = "day"         # 日K线（中长期趋势分析核心周期）
    WEEK = "week"       # 周K线（周度趋势判断）
    MONTH = "month"     # 月K线（月度趋势/基本面分析配套）
    QUARTER = "quar"    # 季度K线（季度业绩匹配分析）
    YEAR = "year"       # 年K线（年度长期趋势分析）

class DividendType(str, Enum):
    """
    复权类型枚举（股票行情复权方式，适配tdxquant行情接口type参数）

    复权用于修正除权除息导致的价格断层，不同复权方式适用于不同分析场景。

    核心使用场景：
    - 行情数据获取时指定复权方式
    - 历史收益回测（后复权更贴合实际收益）
    - 技术分析（前复权更便于价格形态判断）

    枚举值说明（对应行情接口参数）：
    """
    NONE = "none"    # 不复权：原始行情数据，保留除权除息导致的价格跳空，适用于实际交易价格复盘
    FRONT = "front"  # 前复权：以当前价格为基准向前调整历史价格，价格连续无断层，适用于技术形态分析
    BACK = "back"    # 后复权：以历史价格为基准向后调整当前价格，反映真实持仓收益，适用于收益回测

class StockCodeFormat(str, Enum):
    """
    股票代码格式枚举

    用于定义股票代码的不同格式化规则，适配不同数据源/接口的代码格式要求。

    枚举值说明：
    """
    PURE_CODE = "pure_code"    # 纯数字代码（如：600000）
    SUFFIX = "suffix"          # 后缀格式（如：600000.SH）
    PREFIX_DOT = "prefix_dot"  # 前缀+点格式（如：SH.600000）
    PREFIX = "prefix"          # 前缀格式（如：SH600000）

class TradeDateFormat(str, Enum):
    """
    交易日期格式枚举

    定义交易日期/时间的不同字符串格式化规则，适配不同数据源的日期格式要求。

    枚举值分为两类：
    1. 基础日期格式：仅包含年月日
    2. 带时间格式：年月日+时分秒（默认补00:00:00）

    枚举值说明：
    """
    # 基础日期格式
    PURE_NUM = "pure_num"               # 纯数字格式（如：20240520）
    HYPHEN = "hyphen"                   # 连字符分隔（如：2024-05-20）
    SLASH = "slash"                     # 斜杠分隔（如：2024/05/20）
    DOT = "dot"                         # 点分隔（如：2024.05.20）
    CHINESE = "chinese"                 # 中文分隔（如：2024年05月20日）
    
    # 带时间格式（默认补00:00:00）
    HYPHEN_DATETIME = "hyphen_datetime"    # 连字符日期+时间（如：2024-05-20 00:00:00）
    SLASH_DATETIME = "slash_datetime"      # 斜杠日期+时间（如：2024/05/20 00:00:00）
    CHINESE_DATETIME = "chinese_datetime"  # 中文日期+时间（如：2024年05月20日 00:00:00）

    # date 类型
    DATE_CLASS = "date_class"
    # datetime 类型
    DATETIME_CLASS = "datetime_class"

class DataSourceType(str, Enum):
    """
    数据源枚举

    定义量化数据的来源渠道，适配不同数据源的接口封装层。

    枚举值说明：
    """
    BAOSTOCK = "baostock"  # baostock
    TUSHARE = "tushare"    # Tushare（需积分，数据全面）
    AKSHARE = "akshare"    # AkShare（开源财经数据）
    TDXQUANT = "tdxquant"  # 通达信量化接口（本地行情接口）

class DatabaseType(str, Enum):
    """
    数据库类型枚举

    定义数据存储使用的数据库引擎，适配不同存储引擎的读写逻辑。

    枚举值说明：
    """
    SQLITE = "sqlite"    # SQLite（轻量级文件数据库，适合单机部署）
    DUCKDB = "duckdb"    # DuckDB（列式OLAP数据库，适合数据分析）
    MONGODB = "mongodb"  # MongoDB（文档型数据库，适合非结构化数据）

class DbTable(str, Enum):
    """
    数据库表名枚举

    定义量化数据存储的标准表名，确保跨模块表名一致性。

    枚举值说明：
    """
    TRADE_DATE = "trade_date"        # 交易日历表（存储A股交易日信息）
    STOCK_LIST = "stock_list"        # 股票列表表（存储股票基本信息、代码映射等）
    STOCK_DAILY = "stock_daily"      # 股票日线表（存储日K线、成交量、成交额等）
    STOCK_DIVIDEND = "stock_dividend"  # 除权除息表（存储股票分红、送转、配股等信息）
    CAPITAL_DAILY = "capital_daily"  # 每日股本表（存储每日股本数据）
    INDEX_LIST = "index_list"        # 指数列表表
    INDEX_DAILY = "index_daily"      # 指数日线表

class DbView(str, Enum):
    """
    数据库视图名枚举

    定义量化数据存储的标准视图名，确保跨模块视图名一致性。

    枚举值说明：
    """
    STOCK_VIEW = "stock_view"
    STOCK_DIVIDEND_VIEW = "stock_dividend_view"
    INDEX_VIEW = "index_view"
    QFQ_STOCK_DAILY_VIEW = "qfq_stock_daily_view"

class InsertMode(str, Enum):
    """
    数据库批量写入模式枚举
    """
    APPEND = "append"    # 增量追加模式：直接将数据写入尾部
    REPLACE = "replace"  # 覆盖模式：先清空/截断表，再写入全新数据
    IGNORE = "ignore"    # 冲突忽略模式：若主键/唯一索引冲突则自动跳过