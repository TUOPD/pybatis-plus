# -*- coding: utf-8 -*-
"""乐观锁插件（对标 MyBatis-Plus OptimisticLockerInnerInterceptor / @Version）

工作原理（配合 BaseMapper.update_by_id 或含 version 字段的实体更新）：
1. before_update（数据级）：实体上 version 填【当前已读到的版本号】，进 SET 前自动 +1；
2. before_execute（SQL 级）：自动给 UPDATE 追加 `AND version = 旧版本`，
   使并发下“受影响行数 == 0”即可判定乐观锁冲突。

仅对 `SET <version> = 占位符` 且版本号为整数的 UPDATE 生效；非整数/无该写法时不注入。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from pymp.core.db_type import current_placeholder
from pymp.core.exceptions import SqlExecutionError
from pymp.plugin._sql_utils import (
    filters_column,
    inject_where_condition,
    statement_type,
)
from pymp.plugin.interceptor import Interceptor


class OptimisticLockInterceptor(Interceptor):
    """乐观锁：版本号自增 + 更新时按旧版本校验。"""

    def __init__(self, version_field: str = "version"):
        self.version_field = version_field

    # ---------- 数据级：版本号 +1（供 BaseMapper.update_by_id 使用）----------
    def before_update(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if self.version_field in data:
            value = data[self.version_field]
            if value is None:
                raise SqlExecutionError(f"乐观锁字段 {self.version_field} 不能为 None！")
            if isinstance(value, bool) or not isinstance(value, int):
                raise SqlExecutionError(f"乐观锁字段 {self.version_field} 必须为整数！")
            data[self.version_field] = value + 1
        return data

    # ---------- SQL 级：追加 AND version = 旧值 ------------------------------
    def before_execute(self, sql: str, params: List[Any]) -> Tuple[str, List[Any]]:
        if not sql or not str(sql).strip() or statement_type(sql) != "update":
            return sql, params

        ph = current_placeholder()
        # 定位 SET 段里 `version = <占位符>` 的占位符位置
        m = re.search(
            rf"\b{re.escape(self.version_field)}\s*=\s*({re.escape(ph)})",
            sql,
            re.IGNORECASE,
        )
        if not m:
            return sql, params

        # 该占位符之前已有的同风格占位符个数 = 新版本参数在列表中的下标
        idx = sql[: m.start(1)].count(ph)
        values = list(params or [])
        if idx >= len(values):
            return sql, params

        new_version = values[idx]
        if isinstance(new_version, bool) or not isinstance(new_version, int):
            return sql, params  # 非整数无法推导旧值，跳过校验

        # 用户在 WHERE 已显式写过版本条件则不重复追加
        if filters_column(sql, self.version_field):
            return sql, params

        old_version = new_version - 1
        condition = f"{self.version_field} = {ph}"
        new_sql, insert_at = inject_where_condition(sql, condition, ph)
        new_values = values[:insert_at] + [old_version] + values[insert_at:]
        return new_sql, new_values