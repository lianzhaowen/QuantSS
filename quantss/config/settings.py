"""
项目核心配置管理模块（层级嵌套轻量版）
==================================
基于原生 yaml 实现多级嵌套配置。
配置加载优先级（从高到低）：
1. 传入的关键字参数（kwargs）
2. 系统环境变量（大写，形如 QUANTSS_DB_DATABASE_TYPE）
3. config.yaml 配置文件
4. 代码中定义的默认值
"""
import os
import yaml
from typing import Any, Dict
from quantss.utils.app_paths import AppPaths
from quantss.common import DatabaseType, DataSourceType

# 配置文件路径
CONFIG_PATH = os.path.join(AppPaths.config(), 'config.yaml')
ENV_PREFIX = "QUANTSS_"

class ConfigNode:
    """动态配置节点：支持通过 . 访问属性，也支持通过 [] 访问字典"""
    def __init__(self, data: Dict[str, Any]):
        for k, v in data.items():
            if isinstance(v, dict):
                setattr(self, k, ConfigNode(v))
            else:
                setattr(self, k, v)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def to_dict(self) -> Dict[str, Any]:
        """递归转换为标准 Python 字典"""
        res = {}
        for k, v in self.__dict__.items():
            if isinstance(v, ConfigNode):
                res[k] = v.to_dict()
            else:
                res[k] = v
        return res


class Settings:
    """系统全局核心配置类（完美映射 YAML 层级）"""
    
    # 核心硬编码嵌套默认值映射表
    DEFAULTS: Dict[str, Dict[str, Any]] = {
        "app": {
            "PROJECT_NAME": "QuantSS - 股票量化数据系统",
            "ENVIRONMENT": "dev",
            "QUEUE_MAX_SIZE": 150,
            "BATCH_WRITE_SIZE": 10000,
            "MAX_FLUSH_STOCKS": 500,
        },
        "database": {
            "SQLITE_PATH": os.path.join(AppPaths.db(), "qss.db"),
            "DUCKDB_PATH": os.path.join(AppPaths.db(), "qss.duckdb"),
            "SQL_ECHO": False,
            "DATABASE_TYPE": DatabaseType.DUCKDB.value,
        },
        "datasource": {
            "DATASOURCE_TYPE": DataSourceType.TDXQUANT.value,
            "MAX_WORKERS": 5,
            "POOL_TIMEOUT": 15,
        },
        "log": {
            "LOG_LEVEL": "INFO",
            "LOG_MAX_SIZE": 10 * 1024 * 1024,
            "LOG_BACKUP_COUNT": 5,
        },
        "tdx": {
            "TQ_DIR": r"D:\software\new_tdx_test",
            "PYPLUGINS_DIR": r"D:\Software\new_tdx_test\PYPlugins",
            "SYS_DIR": r"D:\Software\new_tdx_test\PYPlugins\sys",
        }
    }

    def __init__(self, file_data: Dict[str, Any] | None = None, **kwargs):
        file_data = file_data or {}
        merged_data = {}

        # 1. 递归融合默认值与 YAML 文件值，并保障基本类型安全
        for section, items in self.DEFAULTS.items():
            merged_data[section] = {}
            file_section = file_data.get(section, {})
            for key, default_val in items.items():
                val = file_section.get(key, default_val)
                merged_data[section][key] = self._cast_type(val, default_val)

        # 2. 构建动态树状属性树，使外部可以调用 settings.db.DATABASE_TYPE
        for section, items in merged_data.items():
            setattr(self, section, ConfigNode(items))

        # 3. 注入环境变量覆盖（形如：export QUANTSS_DB_DATABASE_TYPE=sqlite）
        self._apply_env_overrides()

        # 4. 注入代码手动传入的覆盖参数（形如：Settings(db={"DATABASE_TYPE": "sqlite"})）
        for section, overrides in kwargs.items():
            target_node = getattr(self, section, None)
            if target_node and isinstance(overrides, dict):
                for k, v in overrides.items():
                    upper_k = k.upper()
                    if upper_k in self.DEFAULTS[section]:
                        default_val = self.DEFAULTS[section][upper_k]
                        setattr(target_node, upper_k, self._cast_type(v, default_val))

    def _cast_type(self, val: Any, default_val: Any) -> Any:
        """核心类型安全检查与强制转换"""
        if default_val is None or isinstance(val, type(default_val)):
            return val
        try:
            if isinstance(default_val, bool):
                return str(val).lower() in ("true", "1", "yes", "on")
            return type(default_val)(val)
        except (ValueError, TypeError):
            return default_val

    def _apply_env_overrides(self) -> None:
        """解析形如 QUANTSS_DB_DATABASE_TYPE 的环境变量"""
        for env_key, env_val in os.environ.items():
            if env_key.startswith(ENV_PREFIX):
                # 切割出板块名与配置项名
                parts = env_key[len(ENV_PREFIX):].lower().split("_", 1)
                if len(parts) == 2:
                    section_name, item_name = parts[0], parts[1].upper()
                    if section_name in self.DEFAULTS and item_name in self.DEFAULTS[section_name]:
                        target_node = getattr(self, section_name)
                        default_val = self.DEFAULTS[section_name][item_name]
                        setattr(target_node, item_name, self._cast_type(env_val, default_val))

    def to_dict(self) -> Dict[str, Any]:
        """导出当前内存中的全部嵌套配置字典"""
        return {k: getattr(self, k).to_dict() for k in self.DEFAULTS}


def load_and_init(path: str) -> Settings:
    """加载并初始化配置。若文件不存在则自动吐出包含完美缩进层级的标准 YAML 配置文件"""
    file_data: Dict[str, Any] = {}
    
    # 动态创建配置目录
    dir_name = os.path.dirname(path)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    if not os.path.exists(path):
        print(f"正在生成标准层级化默认配置文件：{path}")
        default_settings = Settings()
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(
                    default_settings.to_dict(), 
                    f, 
                    allow_unicode=True, 
                    sort_keys=False,
                    default_flow_style=False  # 确保输出的是标准的缩进层级缩进，而非花括号 {}
                )
        except Exception as e:
            print(f"⚠️ 自动写入层级 YAML 失败: {e}")
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                file_data = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"⚠️ 读取层级配置文件失败，将采用纯默认代码值: {e}")

    return Settings(file_data=file_data)


# 🏆 全局唯一层级配置单例导出
try:
    settings = load_and_init(CONFIG_PATH)
except Exception as e:
    print(f"❌ 全局配置初始化失败：{str(e)}")
    raise
