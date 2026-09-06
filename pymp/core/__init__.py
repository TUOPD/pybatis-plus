# -*- coding: utf-8 -*-
"""
core 模块的对外统一导出文件
作用：将 core 内部零散的文件组件汇聚在一起，方便外部导入
"""
from pymp.core.constants import (
    DEFAULT_PRIMARY_KEY,
    DEFAULT_PAGE_NO,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PYMYSQL_PLACEHOLDER,
)
from pymp.core.config import Configuration, PoolConfig, global_config
from pymp.core.context import set_connection_provider, get_connection
from pymp.core.exceptions import (
    MpError,
    ConfigurationError,
    SqlExecutionError,
    DuplicateKeyError,
    RecordNotFoundError,
    TooManyResultsError,
)

# 显式指定可以通过 `from pymp.core import *` 导出的清单
__all__ = [
    # 常量
    "DEFAULT_PRIMARY_KEY",
    "DEFAULT_PAGE_NO",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "PYMYSQL_PLACEHOLDER",
    # 配置
    "Configuration",
    "PoolConfig",
    "global_config",
    # 上下文
    "set_connection_provider",
    "get_connection",
    # 异常
    "MpError",
    "ConfigurationError",
    "SqlExecutionError",
    "DuplicateKeyError",
    "RecordNotFoundError",
    "TooManyResultsError",
]