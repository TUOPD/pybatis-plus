# -*- coding: utf-8 -*-
"""
#{name}  -> 占位符 + 参数值（预编译，防注入）
${name}  -> 直接字符串替换（危险，仅用于排序字段/表名等受控场景）
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pymp.core.exceptions import SqlExecutionError
from pymp.utils.safe import (  # ✅ 改动：接入 safe
    sanitize_order_by,
    sanitize_column,
    sanitize_table,
    assert_safe_identifier,
)

_HASH_PARAM = re.compile(r"#\{(\w+)\}")
_DOLLAR_PARAM = re.compile(r"\$\{(\w+)\}")



def render_sql(
    sql_template: str,
    params: Dict[str, Any] | None = None,
    *,
    placeholder: str | None = None,
    # 可选白名单：调用方（Mapper）传入更安全
    column_whitelist: Optional[Sequence[str]] = None,
    table_whitelist: Optional[Sequence[str]] = None,
) -> Tuple[str, List[Any]]:
    params = params or {}
    if placeholder:
        ph = placeholder
    else:
        # 统一走方言解析：SQLite -> '?'，MySQL/PostgreSQL -> '%s'
        from pymp.core.db_type import current_placeholder
        ph = current_placeholder()

    def _dollar_sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in params:
            raise SqlExecutionError(f"SQL 模板缺少 ${{{key}}} 参数")
        raw = params[key]
        if raw is None:
            raise SqlExecutionError(f"${{{key}}} 不能为 None")

        text = str(raw).strip()
        key_l = key.lower()

        # ✅ 按参数名意图分流校验
        if "order" in key_l:
            return sanitize_order_by(text, column_whitelist)
        if "table" in key_l:
            return sanitize_table(text, table_whitelist)
        if any(k in key_l for k in ("column", "col", "field")):
            return sanitize_column(text, column_whitelist)

        # 默认：当标识符
        return assert_safe_identifier(text, what=f"${{{key}}}")

    sql = _DOLLAR_PARAM.sub(_dollar_sub, sql_template)

    names = _HASH_PARAM.findall(sql)
    sql = _HASH_PARAM.sub(ph, sql)
    values = [params.get(n) for n in names]
    return sql, values


def extract_hash_params(sql_template: str) -> List[str]:
    """提取模板里所有 #{name}，便于测试/文档"""
    return _HASH_PARAM.findall(sql_template)