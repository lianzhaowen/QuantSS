"""
数据库测试模块
=============

测试 quantss.database 模块中的数据库操作。
"""

import pytest
import polars as pl
import tempfile
import os

from quantss.database import DuckDBDatabase, SQLiteDatabase
from quantss.models import Stock, TradeDate


class TestDatabase:
    """测试数据库操作"""

    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.duckdb_path = os.path.join(self.temp_dir, "test.duckdb")
        self.sqlite_path = os.path.join(self.temp_dir, "test.sqlite")

    def teardown_method(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_duckdb_connection(self):
        """测试 DuckDB 连接"""
        db = DuckDBDatabase(db_path=self.duckdb_path)
        db.connect()
        assert db is not None
        db.disconnect()

    def test_sqlite_connection(self):
        """测试 SQLite 连接"""
        db = SQLiteDatabase(db_path=self.sqlite_path)
        db.connect()
        assert db is not None
        db.disconnect()

    def test_duckdb_execute_sql(self):
        """测试 DuckDB SQL 执行"""
        db = DuckDBDatabase(db_path=self.duckdb_path)
        db.connect()
        result = db.execute_sql("SELECT 1")
        assert result is not None
        db.disconnect()

    def test_sqlite_execute_sql(self):
        """测试 SQLite SQL 执行"""
        db = SQLiteDatabase(db_path=self.sqlite_path)
        db.connect()
        result = db.execute_sql("SELECT 1")
        assert result is not None
        db.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])