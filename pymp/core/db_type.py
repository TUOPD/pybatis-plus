# pymp/core/db_type.py
# -*- coding: utf-8 -*-
"""
数据库类型自动识别引擎
从 Connection 或 URL 自动推断数据库类型 (MySQL / SQLite / PostgreSQL)
"""
import re
from typing import Any, Optional
from pymp.core.config import global_config
from pymp.sql.dialect import get_dialect, Dialect

_URL_RULES = [
    (re.compile(r"^(mysql|mariadb)", re.I), "mysql"),
    (re.compile(r"^(postgres|postgresql)", re.I), "postgres"),
    (re.compile(r"^sqlite", re.I), "sqlite"),
]

_PRODUCT_RULES = [
    (re.compile(r"mysql|mariadb", re.I), "mysql"),
    (re.compile(r"postgres", re.I), "postgres"),
    (re.compile(r"sqlite", re.I), "sqlite"),
]

_PLACEHOLDER_MAP = {
    "mysql": "%s",
    "postgres": "%s",
    "sqlite": "?",
}


def parse_db_type_from_url(url: str) -> Optional[str]:
    """从数据库 URL 解析 db_type"""
    if not url:
        return None
    match = re.match(r"^([a-zA-Z0-9_+]+)://", url.strip())
    if not match:
        return None
    scheme = match.group(1).split("+")[0]
    for rule, db_type in _URL_RULES:
        if rule.search(scheme):
            return db_type
    return None


def parse_db_type_from_connection(conn: Any) -> Optional[str]:
    """从建立的数据库连接对象推断 db_type"""
    if conn is None:
        return None

    # 特征 1: PyMySQL
    if hasattr(conn, "get_server_info"):
        return "mysql"

    mod = type(conn).__module__ or ""
    name = type(conn).__name__ or ""
    blob = f"{mod} {name}"

    # 特征 2: 类名/模块名推断
    for rule, db_type in _PRODUCT_RULES:
        if rule.search(blob):
            return db_type

    # 特征 3: sqlite3 标准库连接
    try:
        import sqlite3
        if isinstance(conn, sqlite3.Connection):
            return "sqlite"
    except Exception:
        pass

    return None


def resolve_db_type(conn: Any = None) -> str:
    """
    解析最终的 db_type 优先级:
    1. global_config.db_type (手动指定)
    2. 缓存的检测结果
    3. URL 分析
    4. Connection 对象分析
    5. default_db_type
    """
    cfg = global_config

    if cfg.db_type:
        return cfg.db_type.lower()

    if cfg._detected_db_type:
        return cfg._detected_db_type

    detected = None
    if cfg.datasource and cfg.datasource.url:
        detected = parse_db_type_from_url(cfg.datasource.url)

    if not detected and conn is not None:
        detected = parse_db_type_from_connection(conn)

    if not detected:
        detected = cfg.default_db_type

    # 自动缓存检测结果，并刷新全局占位符
    cfg._detected_db_type = detected
    cfg.placeholder = _PLACEHOLDER_MAP.get(detected, cfg.placeholder)
    return detected


def resolve_dialect(conn: Any = None) -> Dialect:
    """获取适配后的 Dialect 方言对象"""
    return get_dialect(resolve_db_type(conn))


def current_placeholder() -> str:
    """返回当前应使用的占位符：SQLite 用 '?'，MySQL/PostgreSQL 用 '%s'。
    统一入口：Query/UpdateWrapper/renderer/插件等一律从这里取，避免各处硬编码。
    """
    return _PLACEHOLDER_MAP.get(resolve_db_type(), "%s")