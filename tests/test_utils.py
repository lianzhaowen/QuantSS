"""
工具函数测试模块
===============

测试 quantss.utils 模块中的工具函数。
"""

import pytest
import polars as pl
import numpy as np
import pandas as pd
import os

from quantss.utils import (
    AppPaths,
    normalize_stock_code,
    normalize_trade_date,
    normalize_index_code,
    get_today_date,
    is_stock,
    is_etf,
    is_index,
)
from quantss.common import StockCodeFormat, TradeDateFormat


class TestAppPaths:
    """测试 AppPaths 类"""

    def test_app_paths_exists(self):
        """测试 AppPaths 各目录是否存在"""
        assert os.path.exists(AppPaths.config())
        assert os.path.exists(AppPaths.log())
        assert os.path.exists(AppPaths.db())

    def test_app_paths_types(self):
        """测试 AppPaths 返回类型"""
        assert isinstance(AppPaths.config(), str)
        assert isinstance(AppPaths.log(), str)
        assert isinstance(AppPaths.db(), str)


class TestStandardize:
    """测试标准化函数"""

    def test_normalize_stock_code(self):
        """测试股票代码标准化"""
        # 默认返回纯代码格式
        assert normalize_stock_code("600000") == "600000"
        assert normalize_stock_code("000001") == "000001"
        # 指定后缀格式
        assert normalize_stock_code("600000", StockCodeFormat.SUFFIX) == "600000.SH"
        assert normalize_stock_code("000001", StockCodeFormat.SUFFIX) == "000001.SZ"
        assert normalize_stock_code("300001", StockCodeFormat.SUFFIX) == "300001.SZ"
        assert normalize_stock_code("600000.SH", StockCodeFormat.SUFFIX) == "600000.SH"
        assert normalize_stock_code("000001.SZ", StockCodeFormat.SUFFIX) == "000001.SZ"

    def test_normalize_index_code(self):
        """测试指数代码标准化"""
        assert normalize_index_code("000001", StockCodeFormat.SUFFIX) == "000001.SH"
        assert normalize_index_code("399001", StockCodeFormat.SUFFIX) == "399001.SZ"
        assert normalize_index_code("000001.SH", StockCodeFormat.SUFFIX) == "000001.SH"

    def test_normalize_trade_date(self):
        """测试交易日期标准化"""
        # 默认返回带连字符格式
        assert normalize_trade_date("2024-01-01") == "2024-01-01"
        assert normalize_trade_date("20240101") == "2024-01-01"
        # 指定纯数字格式
        assert normalize_trade_date("2024-01-01", TradeDateFormat.PURE_NUM) == "20240101"
        assert normalize_trade_date("20240101", TradeDateFormat.PURE_NUM) == "20240101"

    def test_get_today_date(self):
        """测试获取今日日期"""
        today = get_today_date()
        assert len(today) == 10  # YYYY-MM-DD 格式
        assert today.count("-") == 2

    def test_is_stock(self):
        """测试股票判断"""
        assert is_stock("600000") is True
        assert is_stock("000001.SZ") is True
        assert is_stock("300001.SZ") is True

    def test_is_etf(self):
        """测试ETF判断"""
        assert is_etf("510050") is True
        assert is_etf("159901") is True
        assert is_etf("600000") is False

    def test_is_index(self):
        """测试指数判断"""
        assert is_index("000001") is True
        assert is_index("399001") is True
        assert is_index("600000") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])