"""
通用模块测试
============

测试 quantss.common 模块中的常量、枚举和异常。
"""

import pytest

from quantss.common import (
    CHINA_SECURITY_MARKET_ESTABLISH_DATE,
    Exchange,
    KlinePeriod,
    DividendType,
    StockCodeFormat,
    TradeDateFormat,
    DataSourceType,
    DatabaseType,
    DbTable,
    DataSourceException,
    DataProcessException,
    DataStorageException,
    ConfigException,
    DataValidationException,
    BusinessException,
)


class TestConstants:
    """测试常量"""

    def test_china_market_establish_date(self):
        """测试中国股市成立日期"""
        assert CHINA_SECURITY_MARKET_ESTABLISH_DATE is not None
        assert isinstance(CHINA_SECURITY_MARKET_ESTABLISH_DATE, str)


class TestEnums:
    """测试枚举"""

    def test_exchange_enum(self):
        """测试交易所枚举"""
        assert Exchange.SH.value == 'SH'
        assert Exchange.SZ.value == 'SZ'

    def test_kline_period_enum(self):
        """测试 K线周期枚举"""
        assert KlinePeriod.DAY.value == 'day'
        assert KlinePeriod.WEEK.value == 'week'
        assert KlinePeriod.MONTH.value == 'month'

    def test_datasource_type_enum(self):
        """测试数据源类型枚举"""
        # 检查 DataSourceType 有哪些值
        members = [m.name for m in DataSourceType]
        assert len(members) > 0

    def test_database_type_enum(self):
        """测试数据库类型枚举"""
        assert DatabaseType.DUCKDB.value == 'duckdb'
        assert DatabaseType.SQLITE.value == 'sqlite'


class TestExceptions:
    """测试异常类"""

    def test_datasource_exception(self):
        """测试数据源异常"""
        try:
            raise DataSourceException("测试异常")
        except DataSourceException as e:
            assert "测试异常" in str(e)
            assert "[501]" in str(e)

    def test_data_process_exception(self):
        """测试数据处理异常"""
        try:
            raise DataProcessException("处理失败")
        except DataProcessException as e:
            assert "处理失败" in str(e)
            assert "[502]" in str(e)

    def test_config_exception(self):
        """测试配置异常"""
        try:
            raise ConfigException("配置错误")
        except ConfigException as e:
            assert "配置错误" in str(e)
            assert "[504]" in str(e)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])