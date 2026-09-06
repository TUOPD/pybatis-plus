# -*- coding: utf-8 -*-
"""多租户隔离插件（对标 MyBatis-Plus TenantLineInnerInterceptor）：
为 SELECT / UPDATE / DELETE 自动在最外层注入 `tenant_id = ?` 条件。

用法：
    from pymp.plugin import TenantInterceptor, TenantContext

    global_interceptor_chain.add_interceptor(TenantInterceptor())

    with TenantContext(tenant_id=1):
        rows = mapper.select_all()   # 自动拼 tenant_id = 1
"""
from __future__ import annotations

import contextvars
from typing import Any, List, Tuple

from pymp.core.db_type import current_placeholder
from pymp.plugin._sql_utils import (
    filters_column,
    inject_where_condition,
    statement_type,
)
from pymp.plugin.interceptor import Interceptor

# 使用 ContextVar 存储当前请求/协程的租户 ID（线程与异步安全）
current_tenant_id_var: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "current_tenant_id", default=None
)


class TenantContext:
    """上下文管理器：在 with 块内设置当前租户 ID。

    用法:
        with TenantContext(tenant_id=3):
            rows = user_mapper.select_all()
    """

    def __init__(self, tenant_id: Any = None):
        self.tenant_id = tenant_id
        self._token = None

    def __enter__(self) -> "TenantContext":
        self._token = current_tenant_id_var.set(self.tenant_id)
        return self

    def __exit__(self, *exc) -> None:
        if self._token is not None:
            current_tenant_id_var.reset(self._token)


class TenantInterceptor(Interceptor):
    """多租户隔离：设置租户 ID 时自动给最外层查询补租户条件。"""

    def __init__(self, tenant_column: str = "tenant_id"):
        self.tenant_column = tenant_column

    def before_execute(self, sql: str, params: List[Any]) -> Tuple[str, List[Any]]:
        tenant_id = current_tenant_id_var.get()
        if tenant_id is None or not sql or not str(sql).strip():
            return sql, params

        stmt = statement_type(sql)
        if stmt not in ("select", "update", "delete"):
            # INSERT 需要在数据里显式带 tenant_id，插件不自动补
            return sql, params

        # 用户在 WHERE 已显式过滤该列则跳过
        if filters_column(sql, self.tenant_column):
            return sql, params

        ph = current_placeholder()
        condition = f"{self.tenant_column} = {ph}"
        new_sql, idx = inject_where_condition(sql, condition, ph)
        new_params = list(params or [])
        new_params = new_params[:idx] + [tenant_id] + new_params[idx:]
        return new_sql, new_params