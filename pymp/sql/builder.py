# -*- coding: utf-8 -*-
"""
SQL 片段构建器：SELECT / WHERE / ORDER / LIMIT
供 QueryWrapper、BaseMapper 内置 CRUD 复用
"""
from __future__ import annotations

from typing import Any, List, Optional, Sequence, Tuple

from pymp.sql.dialect import Dialect, MySQLDialect


class SqlBuilder:
    def __init__(self, dialect: Dialect | None = None):
        self.dialect = dialect or MySQLDialect()
        self._table: str = ""
        self._columns: str = "*"
        self._wheres: List[str] = []
        self._params: List[Any] = []
        self._order: str = ""
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._sets: List[str] = []
        self._set_params: List[Any] = []

    # ---------- 基础 ----------
    def table(self, table_name: str) -> "SqlBuilder":
        self._table = table_name
        return self

    def select(self, columns: str | Sequence[str] = "*") -> "SqlBuilder":
        if isinstance(columns, str):
            self._columns = columns
        else:
            self._columns = ", ".join(columns) if columns else "*"
        return self

    def where(self, expr: str, *params: Any) -> "SqlBuilder":
        self._wheres.append(expr)
        self._params.extend(params)
        return self

    def and_where(self, expr: str, *params: Any) -> "SqlBuilder":
        return self.where(expr, *params)

    def order_by(self, column: str, desc: bool = False) -> "SqlBuilder":
        direction = "DESC" if desc else "ASC"
        piece = f"{column} {direction}"
        if self._order:
            self._order += f", {piece}"
        else:
            self._order = piece
        return self

    def limit(self, limit: int, offset: Optional[int] = None) -> "SqlBuilder":
        self._limit = limit
        self._offset = offset
        return self

    def set(self, column: str, value: Any) -> "SqlBuilder":
        ph = self.dialect.placeholder
        self._sets.append(f"{column} = {ph}")
        self._set_params.append(value)
        return self

    # ---------- 生成语句 ----------
    def to_select(self) -> Tuple[str, List[Any]]:
        if not self._table:
            raise ValueError("SqlBuilder: table 未设置")
        sql = f"SELECT {self._columns} FROM {self._table}"
        params = list(self._params)
        if self._wheres:
            sql += " WHERE " + " AND ".join(self._wheres)
        if self._order:
            sql += " ORDER BY " + self._order
        if self._limit is not None:
            sql, extra = self.dialect.limit_sql(sql, self._limit, self._offset)
            params.extend(extra)
        return sql, params

    def to_count(self) -> Tuple[str, List[Any]]:
        if not self._table:
            raise ValueError("SqlBuilder: table 未设置")
        sql = f"SELECT COUNT(1) AS cnt FROM {self._table}"
        params = list(self._params)
        if self._wheres:
            sql += " WHERE " + " AND ".join(self._wheres)
        return sql, params

    def to_update(self) -> Tuple[str, List[Any]]:
        if not self._table:
            raise ValueError("SqlBuilder: table 未设置")
        if not self._sets:
            raise ValueError("SqlBuilder: update 缺少 set")
        sql = f"UPDATE {self._table} SET " + ", ".join(self._sets)
        params = list(self._set_params)
        if self._wheres:
            sql += " WHERE " + " AND ".join(self._wheres)
            params.extend(self._params)
        return sql, params

    def to_delete(self) -> Tuple[str, List[Any]]:
        if not self._table:
            raise ValueError("SqlBuilder: table 未设置")
        sql = f"DELETE FROM {self._table}"
        params = list(self._params)
        if self._wheres:
            sql += " WHERE " + " AND ".join(self._wheres)
        return sql, params

    def to_insert(self, data: dict) -> Tuple[str, List[Any]]:
        if not self._table:
            raise ValueError("SqlBuilder: table 未设置")
        if not data:
            raise ValueError("SqlBuilder: insert 数据为空")
        cols = list(data.keys())
        ph = self.dialect.placeholder
        placeholders = ", ".join([ph] * len(cols))
        col_sql = ", ".join(cols)
        sql = f"INSERT INTO {self._table} ({col_sql}) VALUES ({placeholders})"
        return sql, [data[c] for c in cols]

    def clone_where(self) -> "SqlBuilder":
        """复制 where 条件，便于 count + page 两次查询"""
        nb = SqlBuilder(self.dialect)
        nb._table = self._table
        nb._wheres = list(self._wheres)
        nb._params = list(self._params)
        return nb