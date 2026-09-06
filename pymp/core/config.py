# pymp/core/config.py
# -*- coding: utf-8 -*-
"""
pymp 全局运行时配置
控制全局开关：SQL 打印、方言、下划线转驼峰、逻辑删除、数据源等
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from pymp.core.constants import (
    DEFAULT_PRIMARY_KEY,
    DEFAULT_LOGIC_DELETE_COLUMN,
    DEFAULT_LOGIC_DELETED_VAL,
    DEFAULT_LOGIC_NOT_DELETED_VAL,
    DEFAULT_PAGE_NO,
    DEFAULT_PAGE_SIZE,
    PYMYSQL_PLACEHOLDER,
)


@dataclass
class DataSourceConfig:
    """数据源基础配置（对标 spring.datasource）"""
    url: Optional[str] = None          # 例如: mysql://user:pass@127.0.0.1:3306/db
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = ""
    charset: str = "utf8mb4"
    connect_timeout: int = 10


@dataclass
class PoolConfig:
    """数据库连接池配置（对标 DBUtils.PooledDB 常用参数），用于从外部定制连接池。"""
    maxconnections: int = 50   # 连接池允许的最大连接数
    mincached: int = 5         # 启动时/空闲时最少缓存连接数
    maxcached: int = 20        # 空闲时最多缓存连接数
    maxshared: int = 0         # 共享连接最大数（0 = 关闭共享缓存）
    blocking: bool = True      # 池满时是否阻塞等待（False = 直接抛异常）
    maxusage: int = 0          # 单个连接最大复用次数（0 = 不限）
    ping: Optional[int] = 1    # 借出连接前的 ping 检测（-1/1/4 等；None/0 关闭）
    autocommit: bool = False   # 新连接默认是否自动提交


@dataclass
class Configuration:
    """框架全局配置数据类"""
    # 1. 数据源
    datasource: DataSourceConfig = field(default_factory=DataSourceConfig)

    # 1b. 连接池
    pool: PoolConfig = field(default_factory=PoolConfig)

    # 2. 数据库方言 (None 为自动检测，也可手动写死 "mysql" | "sqlite" | "postgres")
    db_type: Optional[str] = None
    default_db_type: str = "mysql"
    placeholder: str = PYMYSQL_PLACEHOLDER

    # 3. 基础约定
    primary_key: str = DEFAULT_PRIMARY_KEY
    map_underscore_to_camel_case: bool = False
    page_no: int = DEFAULT_PAGE_NO
    page_size: int = DEFAULT_PAGE_SIZE

    # 4. 逻辑删除开关
    enable_logic_delete: bool = True
    logic_delete_column: str = DEFAULT_LOGIC_DELETE_COLUMN
    logic_deleted_value: Any = DEFAULT_LOGIC_DELETED_VAL
    logic_not_deleted_value: Any = DEFAULT_LOGIC_NOT_DELETED_VAL

    # 5. 日志控制
    show_sql: bool = True       # True: 把最终可执行 SQL(含模板/参数)打印到控制台
    show_detail: bool = False   # True: 额外打印过程日志（事务/插件改写/动态 SQL 等）

    # 6. 运行时内部缓存
    _detected_db_type: Optional[str] = field(default=None, repr=False)


# 单例全局配置
global_config = Configuration()