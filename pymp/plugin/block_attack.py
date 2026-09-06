# -*- coding: utf-8 -*-
"""防全表更新/删除插件
对标 MyBatis-Plus BlockAttackInnerInterceptor：
在 Executor 执行前拦截“没有 WHERE 条件”的 UPDATE / DELETE，防止误操作清空/改掉整表数据。
"""
from __future__ import annotations

from typing import Any, List, Tuple

from pymp.core.exceptions import SqlExecutionError
from pymp.plugin.interceptor import Interceptor
from pymp.plugin._sql_utils import find_top, statement_type


class BlockAttackInterceptor(Interceptor):
    """拒绝没有 WHERE 条件的 UPDATE / DELETE（防止全表更新/清空事故）。"""

    def before_execute(self, sql: str, params: List[Any]) -> Tuple[str, List[Any]]:
        if not sql or not str(sql).strip():
            return sql, params

        stmt = statement_type(sql)
        if stmt in ("update", "delete"):
            # 顶层没有 WHERE（子查询里的 WHERE 不算），视为全表操作
            if find_top(sql, "where") is None:
                raise SqlExecutionError(
                    "BlockAttackInterceptor: 检测到无 WHERE 条件的全表 "
                    f"{stmt.upper()}，已拦截！请确认业务意图后补充 WHERE 条件，"
                    "或临时移除该拦截器。"
                )
        return sql, params
