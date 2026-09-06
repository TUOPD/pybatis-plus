# -*- coding: utf-8 -*-
"""逻辑删除插件（对标 MyBatis-Plus @TableLogic）：
1. DELETE FROM t WHERE ...  -> UPDATE t SET is_deleted=<已删除值> WHERE ...
2. SELECT ...               -> 自动在最外层补 `AND is_deleted=<未删除值>`

注意：
- 需 Executor 执行前经 before_execute 生效（框架已统一接入）；
- 对应表必须真实存在该列，否则 SELECT 会报 Unknown column；
- 用户在 WHERE 里显式写了该列（例如想查已删除数据）时不会重复注入。
"""
from __future__ import annotations

import re
from typing import Any, List, Tuple

from pymp.core.config import global_config
from pymp.core.db_type import current_placeholder
from pymp.plugin._sql_utils import (
    filters_column,
    inject_where_condition,
    statement_type,
)
from pymp.plugin.interceptor import Interceptor

_DELETE_FROM_RE = re.compile(r"\s*DELETE\s+FROM\s+([`\w.]+)", re.IGNORECASE)


class LogicDeleteInterceptor(Interceptor):
    """逻辑删除：物理 DELETE -> 软删除 UPDATE；SELECT 默认排除已删除行。"""

    def __init__(
        self,
        column: str | None = None,
        deleted_val: Any = None,
        not_deleted_val: Any = None,
    ):
        self.column = column or global_config.logic_delete_column
        self.deleted_val = (
            deleted_val
            if deleted_val is not None
            else global_config.logic_deleted_value
        )
        self.not_deleted_val = (
            not_deleted_val
            if not_deleted_val is not None
            else global_config.logic_not_deleted_value
        )

    def before_execute(self, sql: str, params: List[Any]) -> Tuple[str, List[Any]]:
        if not global_config.enable_logic_delete:
            return sql, params
        if not sql or not str(sql).strip():
            return sql, params

        stmt = statement_type(sql)
        if stmt == "delete":
            return self._rewrite_delete(sql, params)
        if stmt == "select":
            return self._rewrite_select(sql, params)
        return sql, params

    # ---------- DELETE -> 软删除 UPDATE ----------
    def _rewrite_delete(self, sql: str, params: List[Any]) -> Tuple[str, List[Any]]:
        m = _DELETE_FROM_RE.match(sql)
        if not m:
            # 多表 / 带别名等复杂 DELETE 暂不改写
            return sql, params
        table = m.group(1)
        rest = sql[m.end():].strip()
        ph = current_placeholder()
        new_sql = f"UPDATE {table} SET {self.column} = {ph}"
        if rest:
            new_sql += " " + rest
        # SET 占位符位于语句最前 -> 新参数插在原参数最前
        return new_sql, [self.deleted_val, *list(params or [])]

    # ---------- SELECT -> 自动补 is_deleted = 未删除值 ----------
    def _rewrite_select(self, sql: str, params: List[Any]) -> Tuple[str, List[Any]]:
        ph = current_placeholder()
        # 用户在 WHERE 已显式过滤该列（如想看已删除行）则不再追加
        if filters_column(sql, self.column):
            return sql, params
        condition = f"{self.column} = {ph}"
        new_sql, idx = inject_where_condition(sql, condition, ph)
        new_params = list(params or [])
        new_params = new_params[:idx] + [self.not_deleted_val] + new_params[idx:]
        return new_sql, new_params