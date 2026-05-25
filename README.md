# QuantSS - A股量化投资数据管理框架

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

QuantSS 是一个面向A股市场的量化投资数据管理框架，提供多数据源接入、本地数据存储和数据分析能力。

## 主要特性

- **多数据源支持**：通达信、Tushare、AkShare、Baostock 等
- **本地数据存储**：支持 DuckDB（高性能分析）和 SQLite（轻量级）
- **数据标准化**：股票代码、交易日期等标准化处理
- **技术指标计算**：内置常用技术指标（MA、MACD、KDJ、RSI、BOLL 等）
- **Web 数据展示**：基于 Streamlit 的数据可视化管理界面
- **线程安全**：支持多线程并发访问
- **类型安全**：完整的类型注解支持

## 安装

### 基础安装

```bash
pip install -e .
```

### 完整安装（包含所有可选依赖）

```bash
pip install -e ".[all]"
```

### 按需安装

```bash
# 仅安装 Web 界面依赖
pip install -e ".[web]"

# 仅安装通达信数据源
pip install -e ".[tdx]"

# 安装开发依赖
pip install -e ".[dev]"
```

## 快速开始

```python
from quantss.manager.database_manager import database
from quantss.models import StockDaily

# 查询股票日线数据
df = database.select(StockDaily, [("code", "=", "600000"), ("trade_date", ">=", "2024-01-01")])
print(df)
```

## 项目结构

```
QuantSS/
├── quantss/              # 核心库
│   ├── common/           # 通用工具（枚举、常量、异常）
│   ├── config/           # 配置管理
│   ├── database/         # 数据库封装
│   ├── datasource/       # 数据源接口
│   ├── manager/          # 管理器（数据库、数据源）
│   ├── models/           # 数据模型
│   ├── services/         # 业务服务
│   └── utils/            # 工具函数
├── stockweb/             # Web 界面
├── tests/                # 单元测试
└── docs/                 # 文档
```

## 开发

### 代码格式化

```bash
black quantss/ tests/
ruff check quantss/ tests/
```

### 运行测试

```bash
pytest tests/ -v
```

### 类型检查

```bash
mypy quantss/
```

## 许可证

MIT License
