import duckdb
import pyarrow as pa

from typing import Any, Dict, List, Optional, Type
from quantss.common.enums import InsertMode
from quantss.database import SqlDatabase, T
from sqlalchemy.dialects import postgresql as duckdb_compatible_dialect

from quantss.utils import logger

class DuckDBDatabase(SqlDatabase):
    """
    DuckDB 数据库实现类。
    
    基于 DuckDB 引擎提供高性能的数据存储和查询能力，
    支持 PyArrow 数据的零拷贝读写。
    """
    
    def __init__(self, db_path: str = ":memory:"):
        """
        初始化 DuckDB 数据库实例。
        
        Args:
            db_path: 数据库文件路径，默认为内存数据库
        """
        super().__init__()
        self.db_path = db_path
        self.conn = None
        self.dialect = duckdb_compatible_dialect.dialect()

    def _connect(self) -> None:
        """建立 DuckDB 连接"""
        self.conn = duckdb.connect(self.db_path)

    def _disconnect(self) -> None:
        """断开 DuckDB 连接"""
        if self.conn:
            self.conn.close()
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

    def insert(self, model_cls: Type[T], arrow_table: pa.Table) -> Dict[str, int]:
        """
        安全批量插入数据，主键冲突时自动忽略（高性能重写版）。
        
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

        temp_table_name = f"temp_insert_{id(arrow_table)}"
        
        try:
            # 1. 创建临时表并导入数据
            self.conn.execute(f"CREATE TEMP TABLE {temp_table_name} AS SELECT * FROM arrow_table")
            
            # 2. 从 model_cls 获取主键字段
            primary_keys = []
            if hasattr(model_cls, "__fields__"):
                for field_name, field in model_cls.model_fields.items():
                    # SQLModel/Pydantic 的主键定义方式
                    # field 本身就是 FieldInfo 对象
                    extra = getattr(field, "extra", {})
                    is_primary = extra.get("primary_key", False) if isinstance(extra, dict) else False
                    if is_primary or getattr(field, "primary_key", False):
                        primary_keys.append(field_name)
            
            # 如果没有找到主键，尝试从 model_config 获取 unique_keys
            if not primary_keys and hasattr(model_cls, "model_config"):
                unique_keys = model_cls.model_config.get("unique_keys", [])
                if isinstance(unique_keys, list):
                    primary_keys = unique_keys
            
            # 3. 统计插入前的行数
            before_count = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            
            # 4. 使用 DuckDB 的 INSERT OR IGNORE 语法处理主键冲突
            # 或者使用 ON CONFLICT DO NOTHING（DuckDB 0.8+ 支持）
            try:
                # 优先尝试 ON CONFLICT DO NOTHING（更标准）
                sql = f"INSERT INTO {table_name} SELECT * FROM {temp_table_name} ON CONFLICT DO NOTHING"
                self.conn.execute(sql)
            except:
                # 降级使用 INSERT OR IGNORE
                sql = f"INSERT OR IGNORE INTO {table_name} SELECT * FROM {temp_table_name}"
                self.conn.execute(sql)
            
            # 5. 统计插入后的行数
            after_count = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            
            # 计算实际插入行数
            inserted = max(0, after_count - before_count)
            
            # 6. 删除临时表
            self.conn.execute(f"DROP TABLE {temp_table_name}")
            
            return {
                "inserted": inserted, 
                "ignored": max(0, total_rows - inserted)
            }
        except Exception as e:
            # 清理临时表
            try:
                self.conn.execute(f"DROP TABLE IF EXISTS {temp_table_name}")
            except:
                pass
            logger.error(f"[DuckDB] 插入失败: {str(e)}")
            return {"inserted": 0, "ignored": total_rows}

    def batch_insert_ignore(self, model_cls: Type[T], arrow_table: pa.Table) -> Dict[str, int]:
        """
        批量插入数据，主键冲突时自动忽略。
        
        Args:
            model_cls: 模型类
            arrow_table: 待插入的 PyArrow Table
        
        Returns:
            插入结果字典 {"inserted": 插入行数, "ignored": 忽略行数}
        """
        return self.insert(model_cls, arrow_table)

    def select(self, model_cls: Type[T], filters: List[tuple] = None) -> pa.Table:
        """
        条件查询，返回 PyArrow Table。
        
        Args:
            model_cls: 模型类
            filters: 过滤条件列表，格式为 [(列名, 操作符, 值), ...]
        
        Returns:
            查询结果的 PyArrow Table
        """
        table_name = self._get_target_name(model_cls)
        all_columns = [field_name for field_name in model_cls.model_fields.keys()]
        fields = ", ".join([f'"{c}"' for c in all_columns])
        sql = f"SELECT {fields} FROM {table_name}"
        if filters:
            conditions = []
            for col, op, val in filters:
                fmt_val = f"'{val}'" if isinstance(val, str) else str(val)
                conditions.append(f"{col} {op} {fmt_val}")
            sql += " WHERE " + " AND ".join(conditions)
        arrow_table = self.conn.execute(sql).fetch_arrow_table()
        if hasattr(model_cls, "sqlmodel_to_pa_schema"):
            return arrow_table.cast(model_cls.sqlmodel_to_pa_schema())
        return arrow_table

    def update_record(self, model_cls: Type[T], arrow_table: pa.Table, condition_cols: List[str]) -> int:
        """
        批量更新记录。
        
        利用 DuckDB 的内存表 JOIN 特性实现高性能批量更新。
        
        Args:
            model_cls: 模型类
            arrow_table: 待更新的数据（PyArrow Table）
            condition_cols: 条件列列表（用于匹配记录）
        
        Returns:
            受影响的行数
        """
        table_name = self._get_target_name(model_cls)
        total_rows = arrow_table.num_rows
        if total_rows == 0:
            return 0

        all_cols = arrow_table.schema.names
        update_cols = [c for c in all_cols if c not in condition_cols]
        
        # 构建 UPDATE 语句：内存表直接 JOIN 物理表
        set_clause = ", ".join([f"{c} = arrow_table.{c}" for c in update_cols])
        join_clause = " AND ".join([f"{table_name}.{c} = arrow_table.{c}" for c in condition_cols])
        
        sql = f"UPDATE {table_name} SET {set_clause} FROM arrow_table WHERE {join_clause}"
        
        try:
            res = self.conn.execute(sql)
            result = res.fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def delete(self, model_cls: Type[T], filters: List[tuple] = None) -> int:
        """
        条件删除记录。
        
        Args:
            model_cls: 模型类
            filters: 过滤条件列表，格式为 [(列名, 操作符, 值), ...]
        
        Returns:
            操作状态（1 表示成功）
        """
        table_name = self._get_target_name(model_cls)
        sql = f"DELETE FROM {table_name}"
        if filters:
            conditions = [f"{col} {op} '{val}'" if isinstance(val, str) else f"{col} {op} {val}" for col, op, val in filters]
            sql += " WHERE " + " AND ".join(conditions)
        self.conn.execute(sql)
        return 1

    def aggregate(self, model_cls: Type[T], agg_exprs: Dict[str, str], filters: List[tuple] = None) -> pa.Table:
        """
        执行聚合查询。
        
        Args:
            model_cls: 模型类
            agg_exprs: 聚合表达式字典，格式为 {"别名": "聚合表达式"}
            filters: 过滤条件列表
        
        Returns:
            聚合结果的 PyArrow Table
        """
        table_name = self._get_target_name(model_cls)
        select_clause = ", ".join([f"{expr} AS {alias}" for alias, expr in agg_exprs.items()])
        sql = f"SELECT {select_clause} FROM {table_name}"
        
        if filters:
            conditions = []
            for col, op, val in filters:
                fmt_val = f"'{val}'" if isinstance(val, str) else str(val)
                conditions.append(f"{col} {op} {fmt_val}")
            sql += " WHERE " + " AND ".join(conditions)
            
        return self.conn.execute(sql).arrow().read_all()

    def aggregate_groupby(self, model_cls: Type[T], groupby_cols: List[str], agg_exprs: Dict[str, str], filters: List[tuple] = None) -> pa.Table:
        """
        执行分组聚合查询。
        
        Args:
            model_cls: 模型类
            groupby_cols: 分组列名列表
            agg_exprs: 聚合表达式字典，格式为 {"别名": "聚合表达式"}
            filters: 过滤条件列表
        
        Returns:
            分组聚合结果的 PyArrow Table
        """
        table_name = self._get_target_name(model_cls)
        group_select = ", ".join(groupby_cols)
        agg_select = ", ".join([f"{expr} AS {alias}" for alias, expr in agg_exprs.items()])
        sql = f"SELECT {group_select}, {agg_select} FROM {table_name}"
        
        if filters:
            conditions = []
            for col, op, val in filters:
                fmt_val = f"'{val}'" if isinstance(val, str) else str(val)
                conditions.append(f"{col} {op} {fmt_val}")
            sql += " WHERE " + " AND ".join(conditions)
            
        sql += " GROUP BY " + ", ".join(groupby_cols)
        
        return self.conn.execute(sql).arrow().read_all()

    def truncate_table(self, model_cls: Type[T]) -> None:
        """
        清空表数据。
        
        Args:
            model_cls: 模型类
        """
        table_name = self._get_target_name(model_cls)
        self.conn.execute(f"TRUNCATE TABLE {table_name}")

    def execute_sql(self, sql: str, params: Optional[Any] = None, model_cls: Optional[Type[T]] = None) -> Optional[pa.Table]:
        """
        执行自定义 SQL 语句。
        
        Args:
            sql: SQL 语句
            params: 参数（DuckDB 推荐直接在 SQL 中穿透内存变量）
            model_cls: 模型类（用于类型转换）
        
        Returns:
            查询结果的 PyArrow Table，如果是 DDL/DML 语句则返回 None
        """
        res = self.conn.execute(sql)
        
        upper_sql = sql.strip().upper()
        # 如果是 DDL/DML 更改命令，直接返回 None
        if any(upper_sql.startswith(keyword) for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"]):
            return None
            
        # 如果是查询语句，直接提取 Arrow 数据
        arrow_table = res.arrow().read_all()
        
        # 如果指定了模型契约，强制转换类型还原
        if model_cls and hasattr(model_cls, "sqlmodel_to_pa_schema"):
            return arrow_table.cast(model_cls.sqlmodel_to_pa_schema())
        return arrow_table  