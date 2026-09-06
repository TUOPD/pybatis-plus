# -*- coding: utf-8 -*-
"""
数据库方言：占位符、分页、基础能力差异
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class Dialect:
    name: str
    placeholder: str  # %s 或 ?

    def limit_sql(self, sql: str, limit: int, offset: int | None = None) -> Tuple[str, List]:
        """在原 SQL 后追加分页，并返回额外 params"""
        raise NotImplementedError

    def escape_identifier(self, name: str) -> str:
        """表名/字段名简单包裹（防关键字冲突，不做用户输入拼接）"""
        return name


class MySQLDialect(Dialect):
    def __init__(self):
        super().__init__(name="mysql", placeholder="%s")

    def limit_sql(self, sql: str, limit: int, offset: int | None = None) -> Tuple[str, List]:
        if offset is None:
            return f"{sql} LIMIT %s", [limit]
        return f"{sql} LIMIT %s OFFSET %s", [limit, offset]

    def escape_identifier(self, name: str) -> str:
        return f"`{name}`"


class SQLiteDialect(Dialect):
    def __init__(self):
        super().__init__(name="sqlite", placeholder="?")

    def limit_sql(self, sql: str, limit: int, offset: int | None = None) -> Tuple[str, List]:
        # SQLite 也支持 LIMIT/OFFSET，但占位符是 ?
        if offset is None:
            return f"{sql} LIMIT ?", [limit]
        return f"{sql} LIMIT ? OFFSET ?", [limit, offset]

    def escape_identifier(self, name: str) -> str:
        return f'"{name}"'


class PostgresDialect(Dialect):
    def __init__(self):
        super().__init__(name="postgres", placeholder="%s")  # psycopg2 常用 %s

    def limit_sql(self, sql: str, limit: int, offset: int | None = None) -> Tuple[str, List]:
        if offset is None:
            return f"{sql} LIMIT %s", [limit]
        return f"{sql} LIMIT %s OFFSET %s", [limit, offset]

    def escape_identifier(self, name: str) -> str:
        return f'"{name}"'


def get_dialect(name: str = "mysql") -> Dialect:
    name = (name or "mysql").lower()
    if name in ("mysql", "mariadb"):
        return MySQLDialect()
    if name in ("sqlite", "sqlite3"):
        return SQLiteDialect()
    if name in ("postgres", "postgresql", "pg"):
        return PostgresDialect()
    return MySQLDialect()