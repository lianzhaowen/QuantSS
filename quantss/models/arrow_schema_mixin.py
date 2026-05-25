from typing import Union
import pyarrow as pa
from datetime import date, datetime

class ArrowSchemaMixin:
    """
    专为 SQLModel / Pydantic 模型提供 PyArrow Schema 映射功能的混入类。
    支持自动类型提取与主键 Nullable 状态推导。
    """
    @classmethod
    def sqlmodel_to_pa_schema(cls) -> pa.Schema:
        # 使用 Pydantic V2 的 model_fields 属性
        fields_dict = getattr(cls, "model_fields", {})
        
        # 核心 Python 类型到 PyArrow 类型的精密映射
        type_mapping = {
            int: pa.int64(),
            float: pa.float64(),
            str: pa.string(),
            bool: pa.bool_(),
            date: pa.date32(),
            datetime: pa.timestamp('ns'),
        }
        
        pa_fields = []
        
        for field_name, field_meta in fields_dict.items():
            # 提取字段的 Python 原始类型
            field_type = getattr(field_meta, "annotation", getattr(field_meta, "type_", None))
            
            # 剥离 Optional[T] 中的 Union 包装以获取基础类型 T
            if hasattr(field_type, "__origin__") and field_type.__origin__ is Union:
                args = field_type.__args__
                real_types = [arg for arg in args if arg.__name__ != "NoneType"]
                field_type = real_types[0] if real_types else str
            elif hasattr(field_type, "__args__") and len(field_type.__args__) > 0:
                field_type = field_type.__args__[0]

            # 匹配 PyArrow 类型，未定义则默认兜底为 string
            pa_type = type_mapping.get(field_type, pa.string())
            
            # 推导可空属性：SQLModel 主键或显式非空则不允许为 Null
            is_nullable = True
            if hasattr(field_meta, "primary_key") and field_meta.primary_key:
                is_nullable = False
            elif hasattr(field_meta, "nullable") and field_meta.nullable is False:
                is_nullable = False
                
            pa_fields.append(pa.field(field_name, pa_type, nullable=is_nullable))
            
        return pa.schema(pa_fields)