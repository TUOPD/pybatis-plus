# -*- coding: utf-8 -*-
"""Flask 项目的一站式连接池初始化。

- 自动寻找 app 根目录下的 .env 并加载（找不到则读系统环境变量）；
- 数据库连接参数优先级：函数入参 > DB_* 环境变量 > global_config.datasource；
- 连接池参数优先级：函数入参 > POOL_* 环境变量 > global_config.pool。
"""
import os
from pathlib import Path
from typing import Optional

import pymysql
from dbutils.pooled_db import PooledDB
from dotenv import load_dotenv
from flask import Flask
from pymysql.cursors import DictCursor

from pymp.core.bootstrap import configure
from pymp.core.config import PoolConfig, global_config

_db_pool = None


def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _pick_bool(value: Optional[bool], env_key: str, default: bool) -> bool:
    """布尔取值优先级：函数入参 > 环境变量(env_key) > 默认值。"""
    if value is not None:
        return value
    return _env_bool(env_key, default)


def init_pymp_with_pool(
    app: Flask,
    *,
    map_underscore_to_camel_case: bool = False,
    # ---- 日志开关（可选；不传则读 SHOW_SQL/SHOW_DETAIL 环境变量）----
    show_sql: Optional[bool] = None,
    show_detail: Optional[bool] = None,
    # ---- 连接池整体配置（可选，传 PoolConfig 实例即可整体覆盖）----
    pool: Optional[PoolConfig] = None,
    # ---- 数据库连接参数（可选；不传则读 DB_* 环境变量）----
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    charset: Optional[str] = None,
    # ---- 连接池细项（可选；不传则读 POOL_* 环境变量 / global_config.pool）----
    maxconnections: Optional[int] = None,
    mincached: Optional[int] = None,
    maxcached: Optional[int] = None,
    maxshared: Optional[int] = None,
    blocking: Optional[bool] = None,
    maxusage: Optional[int] = None,
    ping: Optional[int] = None,
    autocommit: Optional[bool] = None,
):
    """
    根据传入的 Flask app 实例，自动加载 .env 并建立数据库连接池。

    参数优先级：函数入参 > 环境变量(POOL_*/DB_*) > global_config 默认值。

    用法示例:
        # 1) 全部走 .env，什么都不传（连接池用默认值 50/5/20/blocking/ping=1）
        init_pymp_with_pool(app)

        # 2) 只定制连接池大小
        init_pymp_with_pool(app, maxconnections=100, mincached=10, maxcached=30)

        # 3) 传 PoolConfig 实例整体定制
        init_pymp_with_pool(app, pool=PoolConfig(maxconnections=80, ping=4))

        # 4) 通过 .env / 环境变量定制：
        #    POOL_MAXCONNECTIONS=80 / POOL_MINCACHED=10 / POOL_MAXCACHED=30
        #    POOL_BLOCKING=true / POOL_PING=1 / POOL_AUTOCOMMIT=false
        # 5) 日志开关也可以放 .env：
        #    SHOW_SQL=true   （打印最终可执行 SQL）
        #    SHOW_DETAIL=true（额外打印事务/插件改写等过程日志）
    """
    global _db_pool

    # 🌟 获取【使用该库的 Flask 项目】的根目录 (比如 Test 目录)
    app_root = Path(app.root_path)
    env_path = app_root / ".env"

    # 显式加载使用者项目下的 .env；找不到则从系统环境变量读取
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    ds = global_config.datasource

    # ---- 数据库连接参数：函数入参 > DB_* 环境变量 > global_config.datasource ----
    host = host or os.getenv("DB_HOST") or ds.host
    port = port if port is not None else _env_int("DB_PORT", ds.port)
    user = user or os.getenv("DB_USER") or ds.user
    password = (
        password if password is not None
        else (os.getenv("DB_PASSWORD") or ds.password)
    )
    database = database or os.getenv("DB_NAME") or ds.database
    charset = charset or os.getenv("DB_CHARSET") or ds.charset

    # 防错提示：密码为空，清楚地告知用户搜索了哪个路径
    if not password:
        raise ValueError(
            f"\n❌ [Pybatis-plus Error] 数据库密码为空，导致连接失败！\n"
            f"📍 框架尝试寻找的配置文件路径为: {env_path}\n"
            f"💡 请检查该路径下是否存在 .env 文件，且里面是否配置了 DB_PASSWORD=xxx"
        )

    # 同步回填数据源到 global_config
    ds.host = host
    ds.port = port
    ds.user = user
    ds.password = password
    ds.database = database
    ds.charset = charset

    # ---- 连接池参数：函数入参 > POOL_* 环境变量 > global_config.pool ----
    base = pool if pool is not None else global_config.pool
    maxconnections = maxconnections if maxconnections is not None else _env_int("POOL_MAXCONNECTIONS", base.maxconnections)
    mincached = mincached if mincached is not None else _env_int("POOL_MINCACHED", base.mincached)
    maxcached = maxcached if maxcached is not None else _env_int("POOL_MAXCACHED", base.maxcached)
    maxshared = maxshared if maxshared is not None else _env_int("POOL_MAXSHARED", base.maxshared)
    blocking = blocking if blocking is not None else _env_bool("POOL_BLOCKING", base.blocking)
    maxusage = maxusage if maxusage is not None else _env_int("POOL_MAXUSAGE", base.maxusage)
    ping = ping if ping is not None else _env_int("POOL_PING", base.ping if base.ping is not None else 0)
    autocommit = autocommit if autocommit is not None else _env_bool("POOL_AUTOCOMMIT", base.autocommit)

    # 把“生效后的连接池配置”回填 global_config.pool，便于外部读取
    gp = global_config.pool
    gp.maxconnections = maxconnections
    gp.mincached = mincached
    gp.maxcached = maxcached
    gp.maxshared = maxshared
    gp.blocking = blocking
    gp.maxusage = maxusage
    gp.ping = ping
    gp.autocommit = autocommit

    # 创建连接池
    _db_pool = PooledDB(
        creator=pymysql,
        maxconnections=maxconnections,
        mincached=mincached,
        maxcached=maxcached,
        maxshared=maxshared,
        blocking=blocking,
        maxusage=maxusage,
        ping=ping,
        host=host,
        port=port,
        user=user,
        password=password or "",
        database=database,
        charset=charset,
        cursorclass=DictCursor,
        autocommit=autocommit,
    )

    def get_pooled_connection():
        if _db_pool is None:
            raise RuntimeError("数据库连接池未初始化！")
        return _db_pool.connection()

    # ---- 日志开关：函数入参 > SHOW_SQL/SHOW_DETAIL 环境变量 > 默认值 ----------------
    show_sql = _pick_bool(show_sql, "SHOW_SQL", app.debug)
    show_detail = _pick_bool(show_detail, "SHOW_DETAIL", False)

    configure(
        connection_provider=get_pooled_connection,
        show_sql=show_sql,
        show_detail=show_detail,
        enable_logic_delete=True,
        map_underscore_to_camel_case=map_underscore_to_camel_case,
    )
    print(
        f"✅ Pybatis-plus 连接池已启动 [{env_path}] "
        f"(max={maxconnections}, cached={mincached}~{maxcached}, "
        f"blocking={blocking}, ping={ping}, autocommit={autocommit})"
    )
    print(
        f"   SQL日志={show_sql}, 详情日志={show_detail} "
        f"(可用 .env 的 SHOW_SQL / SHOW_DETAIL 控制)"
    )


def close_pool() -> None:
    """手动关闭连接池（例如应用退出/测试清理时）。"""
    global _db_pool
    if _db_pool is not None:
        try:
            _db_pool.close()
        finally:
            _db_pool = None