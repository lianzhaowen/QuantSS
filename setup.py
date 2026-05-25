"""
QuantSS - A股量化投资数据管理框架
=====================================

支持多数据源接入、本地存储和数据分析的量化投资框架。

主要特性：
- 多数据源支持（通达信、Tushare、AkShare等）
- 本地数据存储（DuckDB、SQLite）
- 技术指标计算
- Web数据展示界面
- 完整的单元测试覆盖
"""

from setuptools import setup, find_packages
import os

# 读取README文件
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# 核心依赖
INSTALL_REQUIRES = [
    # 数据库
    "duckdb>=1.0.0",
    "sqlmodel>=0.0.21",
    "sqlalchemy>=2.0.0",
    
    # 数据处理
    "pyarrow>=15.0.0",
    "polars>=0.20.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    
    # 数据验证
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    
    # 日志和工具
    "loguru>=0.7.0",
    "tqdm>=4.65.0",
    "pyyaml>=6.0",
    
    # 类型支持
    "typing-extensions>=4.8.0",
]

# 可选依赖
EXTRAS_REQUIRE = {
    "web": [
        "streamlit>=1.30.0",
        "plotly>=5.18.0",
    ],
    "tdx": [
        "pytdx>=1.72",
    ],
    "dev": [
        "pytest>=8.0.0",
        "pytest-asyncio>=0.23.0",
        "black>=24.0.0",
        "ruff>=0.3.0",
        "mypy>=1.8.0",
        "pre-commit>=3.6.0",
    ],
}

# 添加all选项
EXTRAS_REQUIRE["all"] = sum(EXTRAS_REQUIRE.values(), [])

setup(
    name="quantss",
    version="0.1.0",
    description="A股量化投资数据管理框架 - 支持多数据源接入、本地存储和数据分析",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="QuantSS Team",
    author_email="quantss@example.com",
    url="https://github.com/quantss/quantss",
    project_urls={
        "Documentation": "https://quantss.readthedocs.io",
        "Source": "https://github.com/quantss/quantss",
        "Tracker": "https://github.com/quantss/quantss/issues",
    },
    packages=find_packages(
        include=["quantss*", "stockweb*"],
        exclude=["tests*", "docs*", "examples*"]
    ),
    package_data={
        "quantss": ["py.typed"],
    },
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    entry_points={
        "console_scripts": [
            "quantss=quantss.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    keywords="quantitative finance a-share stock investment data analysis",
    zip_safe=False,
)
