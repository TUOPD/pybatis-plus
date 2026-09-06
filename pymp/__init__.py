# -*- coding: utf-8 -*-
"""pymp —— 轻量 Python “MyBatis-Plus 风格”数据访问框架。

顶层快捷导出：
    from pymp import configure, set_connection_provider, get_connection
    from pymp import BaseMapper, BaseModel, Page, TableName, TableId
    from pymp import transaction, transactional
"""
from pymp.core.bootstrap import configure
from pymp.core.config import Configuration, DataSourceConfig, PoolConfig, global_config
from pymp.core.context import (
    get_connection,
    get_transaction_connection,
    in_transaction,
    set_connection_provider,
)
from pymp.core.exceptions import (
    ConfigurationError,
    DuplicateKeyError,
    MpError,
    RecordNotFoundError,
    SqlExecutionError,
    TooManyResultsError,
)
from pymp.executor import Executor
from pymp.executor.transaction import transaction, transactional
from pymp.model import (
    BaseModel,
    Field,
    Page,
    TableField,
    TableId,
    TableLogic,
    TableMeta,
    TableName,
    inspect_table_meta,
)
from pymp.mapper import BaseMapper, CrudMethods, register_mapper
from pymp.plugin import (
    AutoFillInterceptor,
    BlockAttackInterceptor,
    Interceptor,
    InterceptorChain,
    LogicDeleteInterceptor,
    OptimisticLockInterceptor,
    TenantContext,
    TenantInterceptor,
    global_interceptor_chain,
)

__version__ = "0.1.0"

__all__ = [
    # 配置 / 引导
    "configure",
    "Configuration",
    "DataSourceConfig",
    "PoolConfig",
    "global_config",
    # 连接上下文
    "set_connection_provider",
    "get_connection",
    "in_transaction",
    "get_transaction_connection",
    # 异常
    "MpError",
    "ConfigurationError",
    "SqlExecutionError",
    "DuplicateKeyError",
    "RecordNotFoundError",
    "TooManyResultsError",
    # 执行
    "Executor",
    "transaction",
    "transactional",
    # 模型
    "BaseModel",
    "Page",
    "Field",
    "TableMeta",
    "TableName",
    "TableId",
    "TableLogic",
    "TableField",
    "inspect_table_meta",
    # Mapper
    "BaseMapper",
    "CrudMethods",
    "register_mapper",
    # 插件
    "Interceptor",
    "InterceptorChain",
    "global_interceptor_chain",
    "AutoFillInterceptor",
    "LogicDeleteInterceptor",
    "OptimisticLockInterceptor",
    "TenantInterceptor",
    "TenantContext",
    "BlockAttackInterceptor",
]
