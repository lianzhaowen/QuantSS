"""
数据模型测试模块
===============

测试 quantss.models 模块中的数据模型。
"""

import pytest
import polars as pl
import pyarrow as pa

from quantss.models import (
    Stock,
    TradeDate,
    StockDaily,
    StockDividend,
    CapitalDaily,
    Index,
    IndexDaily,
)


class TestModels:
    """测试数据模型"""

    def test_stock_model_exists(self):
        """测试 Stock 模型存在"""
        assert Stock is not None

    def test_trade_date_model_exists(self):
        """测试 TradeDate 模型存在"""
        assert TradeDate is not None

    def test_stock_daily_model_exists(self):
        """测试 StockDaily 模型存在"""
        assert StockDaily is not None

    def test_stock_dividend_model_exists(self):
        """测试 StockDividend 模型存在"""
        assert StockDividend is not None

    def test_stock_model_columns(self):
        """测试 Stock 模型列定义"""
        # 检查必需字段是否存在
        assert hasattr(Stock, 'code')
        assert hasattr(Stock, 'name')

    def test_stock_daily_model_columns(self):
        """测试 StockDaily 模型列定义"""
        assert hasattr(StockDaily, 'code')
        assert hasattr(StockDaily, 'trade_date')
        assert hasattr(StockDaily, 'open')
        assert hasattr(StockDaily, 'high')
        assert hasattr(StockDaily, 'low')
        assert hasattr(StockDaily, 'close')
        assert hasattr(StockDaily, 'volume')


class TestModelSchemas:
    """测试模型 Schema"""

    def test_stock_pa_schema_exists(self):
        """测试 Stock PA Schema 存在"""
        from quantss.models import STOCK_PA_SCHEMA
        assert STOCK_PA_SCHEMA is not None
        assert isinstance(STOCK_PA_SCHEMA, pa.Schema)

    def test_stock_daily_pa_schema_exists(self):
        """测试 StockDaily PA Schema 存在"""
        from quantss.models import STOCKDAILY_PA_SCHEMA
        assert STOCKDAILY_PA_SCHEMA is not None
        assert isinstance(STOCKDAILY_PA_SCHEMA, pa.Schema)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])