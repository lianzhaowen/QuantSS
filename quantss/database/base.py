import pyarrow as pa

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from sqlmodel import SQLModel
from quantss.common.enums import InsertMode
from quantss.models.arrow_schema_mixin import ArrowSchemaMixin

T = TypeVar("T", bound=Union[ArrowSchemaMixin, SQLModel])

class BaseDatabase(ABC):

    def __init__(self):
        self.connected = False

    def connect(self) -> None:
        """【模板方法】统一的连接入口，控制状态机并分发具体的物理连接"""
        if self.connected:
            return
        
        self._connect()
        self.connected = True

    def disconnect(self) -> None:
        """【模板方法】统一的断开入口"""
        if not self.connected:
            return

        self._disconnect()
        self.connected = False

    @abstractmethod
    def _connect(self) -> None:
        """由具体的数据库子类去实现真正的驱动连接细节"""
        pass

    @abstractmethod
    def _disconnect(self) -> None:
        """由具体的数据库子类去实现真正的驱动断开细节"""
        pass

    # =================== 通用基础CRUD（全库统一入参、统一返回） =================== #
    @abstractmethod
    def insert(self, model_cls: Type[T], arrow_table: pa.Table) -> Dict[str, int]:
        """【Create】安全批量插入数据（主键冲突自动忽略）"""
        pass

    @abstractmethod
    def batch_insert_ignore(self, model_cls: Type[T], arrow_table: pa.Table) -> Dict[str, int]:
        """
        【Create】极限吞吐量防重插入。
        适用于海量因子、时序行情落库。利用原生 C++ 级批量去重，绕过逐行扫描。
        """
        pass

    @abstractmethod
    def select(self, model_cls: Type[T], filters: List[tuple] = None) -> pa.Table:
        """【Read】条件查询，直接返回高性能 PyArrow Table"""
        pass

    @abstractmethod
    def update_record(self, model_cls: Type[T], arrow_table: pa.Table, condition_cols: List[str]) -> int:
        """【Update】精确更新历史记录，返回受影响行数"""
        pass

    @abstractmethod
    def delete(self, model_cls: Type[T], filters: List[tuple] = None) -> int:
        """【Delete】条件批量删除时序历史数据，返回删除行数"""
        pass

    @abstractmethod
    def aggregate(
        self, 
        model_cls: Type[T], 
        agg_exprs: Dict[str, str], 
        filters: List[tuple] = None
    ) -> pa.Table:
        """
        【Read】执行聚合查询（无分组）。
        
        Args:
            model_cls: 模型类
            agg_exprs: 聚合表达式字典，格式为 {"别名": "聚合表达式"}，如 {"total": "SUM(amount)"}
            filters: 过滤条件列表，格式为 [(列名, 操作符, 值), ...]
        
        Returns:
            PyArrow Table，包含聚合结果
        """
        pass

    @abstractmethod
    def aggregate_groupby(
        self, 
        model_cls: Type[T], 
        groupby_cols: List[str], 
        agg_exprs: Dict[str, str], 
        filters: List[tuple] = None
    ) -> pa.Table:
        """
        【Read】执行分组聚合查询。
        
        Args:
            model_cls: 模型类
            groupby_cols: 分组列名列表
            agg_exprs: 聚合表达式字典，格式为 {"别名": "聚合表达式"}，如 {"avg_close": "AVG(close)"}
            filters: 过滤条件列表，格式为 [(列名, 操作符, 值), ...]
        
        Returns:
            PyArrow Table，包含分组聚合结果
        """
        pass

    @abstractmethod
    def truncate_table(self, model_cls: Type[T]) -> None:
        """【Delete】直接清空并重置整张数据表，速度极快（规避逐行删除开销）"""
        pass

    @abstractmethod
    def create_tables_from_models(self, models: List[Type[SQLModel]]) -> None:
        """
        根据SQLModel自动创建表、索引（含唯一索引），支持视图创建。
        
        规则：
        1. 若模型Config有stmt属性，则创建视图（跳过建表）
        2. 自动创建表（IF NOT EXISTS）
        3. 自动创建模型定义的普通索引（IF NOT EXISTS）
        4. 根据Config.unique_keys创建唯一索引（IF NOT EXISTS）
        
        Args:
            models: SQLModel类列表
        """
        pass

    @abstractmethod
    def execute_sql(self, sql: str, params: Optional[Any] = None, model_cls: Optional[Type[T]] = None) -> Optional[pa.Table]:
        pass

    def truncate_all_tables(self, confirm: bool = False) -> Dict[str, int]: 
        """
        【高危操作】清空系统内注册的所有历史时序数据表（保留表结构与索引）。
        """
        if not confirm:
            raise ValueError("❌ 危险操作：清空全库数据必须显式指定 confirm=True")
            
        # 引入全局的模型注册表
        from quantss.models import ALL_MODELS
        
        cleared_count = 0
        for model in ALL_MODELS:
            # ⚠️ 规则：只清空物理表，跳过有 __viewname__ __view__ stmt 配置的虚拟视图（视图无法执行 TRUNCATE）
            # 兼容新旧两种配置方式：model.Config.stmt / model.stmt, model.Config.__viewname__ / model.model_config["__viewname__"]
            has_view_config = False
            if hasattr(model, "Config"):
                has_view_config = any(getattr(model.Config, attr, None) is not None for attr in ["__viewname__", "__view__", "stmt"])
            if not has_view_config:
                has_view_config = getattr(model, "stmt", None) is not None or (hasattr(model, "model_config") and model.model_config.get("__viewname__"))
            if has_view_config:
                continue
                
            # 传入模型类对象本身，完美对齐具体的子类接口契约
            self.truncate_table(model)
            cleared_count += 1
            
        return {"tables_cleared": cleared_count}

class SqlDatabase(BaseDatabase): 

    def __init__(self):
        super().__init__()
        self.dialect = None

    def create_tables_from_models(self, models: List[Type[SQLModel]]) -> None:
        from sqlalchemy.schema import CreateTable, CreateIndex

        for model in models:
            # ====================== 核心：1.自动创建视图 ======================
            # 兼容新旧两种配置方式：model.Config.stmt / model.stmt
            stmt = None
            view_name = None
            if hasattr(model, "Config") and hasattr(model.Config, "stmt"):
                stmt = model.Config.stmt
                view_name = getattr(model.Config, "__viewname__", model.__name__.lower())
            elif getattr(model, "stmt", None) is not None:
                stmt = model.stmt
                view_name = model.model_config.get("__viewname__", model.__name__.lower())
            
            if stmt is not None:
                # 生成 SQL
                sql = str(stmt.compile(compile_kwargs={"literal_binds": True}, dialect=self.dialect))
                create_view_sql = f"CREATE OR REPLACE VIEW {view_name} AS {sql}"
                self.execute_sql(create_view_sql)
                continue  # 跳过建表逻辑

            table = model.__table__
            # ====================== 2. 建表 ======================
            sql = str(CreateTable(table))
            sql = sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
            self.execute_sql(sql)

            # ====================== 3. 自动创建所有普通索引 ======================
            for index in table.indexes:
                ix_sql = str(CreateIndex(index))
                ix_sql = ix_sql.replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS")
                self._raw_execute(ix_sql)

            # ====================== 4. 自动根据 Config.unique_keys 创建唯一索引 ======================
            if hasattr(model, "Config") and hasattr(model.Config, "unique_keys"):
                table_name = model.__tablename__
                keys = model.Config.unique_keys
                key_str = ", ".join(keys)
                index_name = f"uq_{table_name}_{'_'.join(keys)}"

                # 自动创建唯一索引
                self.execute_sql(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name} ({key_str})"
                )

