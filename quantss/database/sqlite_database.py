"""
SQLite 数据库实现模块
====================

基于 SQLite 引擎提供轻量级数据存储和查询能力。

核心特性：
- 轻量级：无需独立服务器，文件式数据库
- 跨平台：支持 Windows、Linux、macOS
- ACID 事务：支持完整的事务处理
- 零配置：开箱即用，无需额外配置

注意：
- SQLite 适合单机应用和小型数据集
- 高并发场景建议使用 DuckDB 或其他数据库
"""

import sqlite3
import pyarrow as pa

from sqlalchemy.dialects import sqlite as sqlite_dialect
from typing import Any, Dict, Optional, Type, List
from quantss.common.enums import InsertMode
from quantss.database import SqlDatabase, T


class SQLiteDatabase(SqlDatabase):
    """
    SQLite 数据库实现类。
    
    基于 SQLite 引擎提供轻量级数据存储和查询能力，
    适合单机应用和小型数据集场景。
    """

    def __init__(self, db_path: str = ":memory:"):
        """
        初始化 SQLite 数据库实例。
        
        Args:
            db_path: 数据库文件路径，默认为内存数据库（:memory:）
        
        Note:
            - 使用 ":memory:" 创建内存数据库，数据在程序退出后丢失
            - 使用文件路径创建持久化数据库，数据会保存到磁盘
        """
        super().__init__()
        self.db_path = db_path
        self.conn = None
        self.dialect = sqlite_dialect.dialect()

    def _connect(self) -> None:
        """
        建立 SQLite 连接。
        
        配置 SQLite 连接参数：
        - check_same_thread: 设为 False 允许多线程共享连接
        - isolation_level: 设为 None 使用自动提交模式
        """
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None
        )

    def _disconnect(self) -> None:
        """
        断开 SQLite 连接。
        
        关闭数据库连接并释放资源。
        """
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            finally:
                self.conn = None

    def _get_target_name(self, model_cls: Type[T]) -> str:
        """
        获取目标表名。
        
        优先使用模型的 __viewname__（支持 Config.__viewname__ 和 model_config["__viewname__"]），
        其次使用 __tablename__，最后使用类名的小写形式。
        
        Args:
            model_cls: 模型类
        
        Returns:
            目标表名
        """
        # 兼容新旧两种配置方式
        view_name = None
        if hasattr(model_cls, "Config"):
            view_name = getattr(model_cls.Config, "__viewname__", None)
        if view_name is None and hasattr(model_cls, "model_config"):
            view_name = model_cls.model_config.get("__viewname__")
        return view_name or getattr(model_cls, "__tablename__", model_cls.__name__.lower())

    def _execute_arrow_batch(self, sql: str, arrow_table: pa.Table):
        """
        将 PyArrow Table 数据批量写入 SQLite。
        
        Args:
            sql: SQL 语句模板（使用 ? 作为占位符）
            arrow_table: 待插入的 PyArrow Table
        
        Returns:
            执行结果游标
        """
        cols_list = arrow_table.schema.names
        bind_params = list(zip(*(arrow_table.column(col).to_pylist() for col in cols_list)))
        return self.conn.executemany(sql, bind_params)

    def insert(self, model_cls: Type[T], arrow_table: pa.Table) -> Dict[str, int]:
        """
        安全批量插入数据，主键冲突时自动忽略。
        
        Args:
            model_cls: 模型类
            arrow_table: 待插入的 PyArrow Table
        
        Returns:
            插入结果字典 {"inserted": 插入行数, "ignored": 忽略行数}
        """
        table_name = self._get_target_name(model_cls)
        total_rows = arrow_table.num_rows
        
        if total_rows == 0:
            return {"inserted": 0, "ignored": 0}

        cols = ", ".join(arrow_table.schema.names)
        holders = ", ".join(["?"] * len(arrow_table.schema.names))
        sql = f"INSERT OR IGNORE INTO {table_name} ({cols}) VALUES ({holders})"
        
        try:
            res = self._execute_arrow_batch(sql, arrow_table)
            inserted = res.rowcount
            if inserted < 0:
                inserted = total_rows
            return {
                "inserted": inserted,
                "ignored": max(0, total_rows - inserted)
            }
        except Exception as e:
            return {"inserted": 0, "ignored": total_rows}

    def batch_insert_ignore(self, model_cls: Type[T], arrow_table: pa.Table) -> Dict[str, int]:
        """
        批量插入数据，主键冲突时自动忽略（同 insert 方法）。
        
        Args:
            model_cls: 模型类
            arrow_table: 待插入的 PyArrow Table
        
        Returns:
            插入结果字典 {"inserted": 插入行数, "ignored": 忽略行数}
        """
        return self.insert(model_cls, arrow_table)

    def select(self, model_cls: Type[T], filters: List[tuple] = None) -> pa.Table:
        """
        条件查询数据，返回 PyArrow Table。
        
        Args:
            model_cls: 模型类
            filters: 查询条件列表，每个条件为 (列名, 操作符, 值) 元组
        
        Returns:
            PyArrow Table，包含查询结果
        
        Example:
            filters = [("code", "=", "600000"), ("trade_date", ">=", "2024-01-01")]
            result = db.select(StockDaily, filters)
        """
        table_name = self._get_target_name(model_cls)
        sql = f"SELECT * FROM {table_name}"
        params = []

        if filters:
            conditions = [f"{col} {op} ?" for col, op, val in filters]
            sql += " WHERE " + " AND ".join(conditions)
            params = [val for _, _, val in filters]

        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            if hasattr(model_cls, "sqlmodel_to_pa_schema"):
                return pa.Table.from_pylist([], schema=model_cls.sqlmodel_to_pa_schema())
            return pa.Table.from_pylist([])

        colnames = [desc[0] for desc in cursor.description]
        pydict = {col: [row[i] for row in rows] for i, col in enumerate(colnames)}

        if hasattr(model_cls, "sqlmodel_to_pa_schema"):
            return pa.Table.from_pydict(pydict, schema=model_cls.sqlmodel_to_pa_schema())
        return pa.Table.from_pydict(pydict)

    def update_record(self, model_cls: Type[T], arrow_table: pa.Table, condition_cols: List[str]) -> int:
        """
        精确更新历史记录。
        
        Args:
            model_cls: 模型类
            arrow_table: 待更新的数据（PyArrow Table）
            condition_cols: 作为更新条件的列名列表
        
        Returns:
            受影响的行数
        """
        table_name = self._get_target_name(model_cls)
        total_rows = arrow_table.num_rows
        
        if total_rows == 0:
            return 0

        all_cols = arrow_table.schema.names
        update_cols = [c for c in all_cols if c not in condition_cols]
        
        # 动态组装带有 ? 占位符的 UPDATE 语句
        set_clause = ", ".join([f"{c} = ?" for c in update_cols])
        where_clause = " AND ".join([f"{c} = ?" for c in condition_cols])
        sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
        
        # 严格按照 SQL 语句中占位符的顺序（先 SET 列，后 WHERE 列）重新重构参数矩阵
        ordered_cols = update_cols + condition_cols
        bind_params = list(zip(*(arrow_table.column(col).to_pylist() for col in ordered_cols)))
        
        try:
            res = self.conn.executemany(sql, bind_params)
            return res.rowcount
        except Exception as e:
            return 0

    def delete(self, model_cls: Type[T], filters: List[tuple] = None) -> int:
        """
        条件批量删除数据。
        
        Args:
            model_cls: 模型类
            filters: 删除条件列表，每个条件为 (列名, 操作符, 值) 元组
        
        Returns:
            删除的行数
        """
        table_name = self._get_target_name(model_cls)
        sql = f"DELETE FROM {table_name}"
        params = []

        if filters:
            conditions = [f"{col} {op} ?" for col, op, val in filters]
            sql += " WHERE " + " AND ".join(conditions)
            params = [val for _, _, val in filters]

        res = self.conn.execute(sql, params)
        return res.rowcount

    def aggregate(self, model_cls: Type[T], agg_exprs: Dict[str, str], filters: List[tuple] = None) -> pa.Table:
        """
        聚合查询（无分组）。
        
        Args:
            model_cls: 模型类
            agg_exprs: 聚合表达式字典，key 为别名，value 为聚合表达式
            filters: 查询条件列表
        
        Returns:
            PyArrow Table，包含聚合结果
        
        Example:
            agg_exprs = {"total_volume": "SUM(volume)", "avg_close": "AVG(close)"}
            result = db.aggregate(StockDaily, agg_exprs, [("trade_date", ">=", "2024-01-01")])
        """
        table_name = self._get_target_name(model_cls)
        select_clause = ", ".join([f"{expr} AS {alias}" for alias, expr in agg_exprs.items()])
        sql = f"SELECT {select_clause} FROM {table_name}"
        
        params = []
        if filters:
            conditions = [f"{col} {op} ?" for col, op, val in filters]
            sql += " WHERE " + " AND ".join(conditions)
            params = [val for _, _, val in filters]
            
        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()
        
        if not rows:
            return pa.Table.from_pylist([])
            
        colnames = [desc[0] for desc in cursor.description]
        pydict = {col: [row[i] for row in rows] for i, col in enumerate(colnames)}
        return pa.Table.from_pydict(pydict)

    def aggregate_groupby(self, model_cls: Type[T], groupby_cols: List[str], agg_exprs: Dict[str, str], filters: List[tuple] = None) -> pa.Table:
        """
        分组聚合查询。
        
        Args:
            model_cls: 模型类
            groupby_cols: 分组列名列表
            agg_exprs: 聚合表达式字典，key 为别名，value 为聚合表达式
            filters: 查询条件列表
        
        Returns:
            PyArrow Table，包含分组聚合结果
        
        Example:
            groupby_cols = ["code"]
            agg_exprs = {"total_volume": "SUM(volume)", "max_high": "MAX(high)"}
            result = db.aggregate_groupby(StockDaily, groupby_cols, agg_exprs)
        """
        table_name = self._get_target_name(model_cls)
        group_select = ", ".join(groupby_cols)
        agg_select = ", ".join([f"{expr} AS {alias}" for alias, expr in agg_exprs.items()])
        sql = f"SELECT {group_select}, {agg_select} FROM {table_name}"
        
        params = []
        if filters:
            conditions = [f"{col} {op} ?" for col, op, val in filters]
            sql += " WHERE " + " AND ".join(conditions)
            params = [val for _, _, val in filters]
            
        sql += " GROUP BY " + ", ".join(groupby_cols)
        
        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()
        
        if not rows:
            return pa.Table.from_pylist([])
            
        colnames = [desc[0] for desc in cursor.description]
        pydict = {col: [row[i] for row in rows] for i, col in enumerate(colnames)}
        return pa.Table.from_pydict(pydict)

    def truncate_table(self, model_cls: Type[T]) -> None:
        """
        清空表数据。
        
        Args:
            model_cls: 模型类
        
        Note:
            SQLite 没有 TRUNCATE TABLE 语句，使用 DELETE 替代
            同时重置自增计数器
        """
        table_name = self._get_target_name(model_cls)
        self.conn.execute(f"DELETE FROM {table_name}")
        self.conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")

    def execute_sql(self, sql: str, params: Optional[Any] = None, model_cls: Optional[Type[T]] = None) -> Optional[pa.Table]:
        """
        执行任意 SQL 语句。
        
        Args:
            sql: SQL 语句
            params: 参数列表（可选）
            model_cls: 模型类（用于结果类型转换，可选）
        
        Returns:
            SELECT 查询返回 PyArrow Table，其他语句返回 None
        """
        cursor = self.conn.execute(sql, params) if params is not None else self.conn.execute(sql)
        
        # 自动事务提交（针对 DDL / DML 语句）
        upper_sql = sql.strip().upper()
        if any(upper_sql.startswith(keyword) for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"]):
            return None

        # 如果是 SELECT 查询语句，将其解析为 pyarrow.Table
        rows = cursor.fetchall()
        if not rows:
            if model_cls and hasattr(model_cls, "sqlmodel_to_pa_schema"):
                return pa.Table.from_pylist([], schema=model_cls.sqlmodel_to_pa_schema())
            return pa.Table.from_pylist([])

        colnames = [desc[0] for desc in cursor.description]
        pydict = {col: [row[i] for row in rows] for i, col in enumerate(colnames)}
        
        # 如果指定了模型契约，强制转换类型还原
        if model_cls and hasattr(model_cls, "sqlmodel_to_pa_schema"):
            return pa.Table.from_pydict(pydict, schema=model_cls.sqlmodel_to_pa_schema())
        return pa.Table.from_pydict(pydict)
