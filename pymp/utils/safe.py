# -*- coding: utf-8 -*-
"""
安全工具：
- 列名/表名/排序字段白名单校验（防 ${} 与 order by 注入）
- 简单 SQL 标识符校验
- 危险关键字检测（辅助，不能替代参数绑定）
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Set

from pymp.core.exceptions import SqlExecutionError


# 合法标识符：table / column / table.column / `col` / "col"
_IDENT_RE = re.compile(
    r"^`?[A-Za-z_][A-Za-z0-9_]*`?(\.`?[A-Za-z_][A-Za-z0-9_]*`?)?$"
)
_ORDER_ITEM_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?(\s+(ASC|DESC))?$",
    re.IGNORECASE,
)
_MULTI_ORDER_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?"
    r"(\s*,\s*[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?)*$",
    re.IGNORECASE,
)

# 出现在“标识符位置”时的危险片段
_DANGEROUS_SQL_RE = re.compile(
    r"[;'\"]|--|/\*|\*/|\b(union|select|insert|update|delete|drop|alter|exec|execute)\b",
    re.IGNORECASE,
)


class SafeNameError(SqlExecutionError):
    """非法表名/列名/排序字段"""
    pass


def is_safe_identifier(name: str) -> bool:
    """是否像合法表名/列名（不含空格、表达式）"""
    if not name or not isinstance(name, str):
        return False
    name = name.strip()
    if not name or len(name) > 128:
        return False
    if _DANGEROUS_SQL_RE.search(name):
        return False
    return bool(_IDENT_RE.match(name))


def is_safe_order_by(expr: str) -> bool:
    """
    是否像安全的 ORDER BY 表达式：
      created_at
      created_at DESC
      created_at ASC, id DESC
    不允许函数、子查询、分号等
    """
    if not expr or not isinstance(expr, str):
        return False
    expr = expr.strip()
    if not expr or len(expr) > 256:
        return False
    if _DANGEROUS_SQL_RE.search(expr):
        return False
    return bool(_MULTI_ORDER_RE.match(expr) or _ORDER_ITEM_RE.match(expr))


def assert_safe_identifier(name: str, *, what: str = "identifier") -> str:
    """校验标识符，失败抛 SafeNameError；成功返回 strip 后的 name"""
    n = (name or "").strip()
    if not is_safe_identifier(n):
        raise SafeNameError(f"非法{what}: {name!r}")
    return n.strip("`").strip('"')


def assert_safe_order_by(expr: str) -> str:
    e = (expr or "").strip()
    if not is_safe_order_by(e):
        raise SafeNameError(f"非法 ORDER BY 表达式: {expr!r}")
    return e


def assert_in_whitelist(
    name: str,
    whitelist: Iterable[str],
    *,
    what: str = "column",
) -> str:
    """
    白名单校验（最强防护）
    whitelist: 允许的列名/表名集合
    """
    n = (name or "").strip().strip("`").strip('"')
    allowed: Set[str] = {str(x).strip().strip("`").strip('"') for x in whitelist}
    if n not in allowed:
        raise SafeNameError(
            f"{what} 不在白名单中: {name!r}；允许: {sorted(allowed)}"
        )
    return n


def sanitize_column(
    name: str,
    whitelist: Optional[Iterable[str]] = None,
) -> str:
    """
    清洗列名：
    - 有白名单：必须命中白名单
    - 无白名单：至少通过标识符校验
    """
    if whitelist is not None:
        return assert_in_whitelist(name, whitelist, what="column")
    return assert_safe_identifier(name, what="column")


def sanitize_columns(
    names: Sequence[str],
    whitelist: Optional[Iterable[str]] = None,
) -> List[str]:
    return [sanitize_column(n, whitelist) for n in names]


def sanitize_table(
    name: str,
    whitelist: Optional[Iterable[str]] = None,
) -> str:
    if whitelist is not None:
        return assert_in_whitelist(name, whitelist, what="table")
    return assert_safe_identifier(name, what="table")


def sanitize_order_by(
    expr: str,
    whitelist: Optional[Iterable[str]] = None,
) -> str:
    """
    校验 ORDER BY。
    若提供 whitelist，会把每个排序列（去掉 ASC/DESC）拿去白名单检查。
    """
    e = assert_safe_order_by(expr)
    if whitelist is None:
        return e

    parts = [p.strip() for p in e.split(",")]
    cleaned = []
    for part in parts:
        bits = part.split()
        col = bits[0]
        direction = bits[1].upper() if len(bits) > 1 else ""
        col = assert_in_whitelist(col, whitelist, what="order_by column")
        cleaned.append(f"{col} {direction}".strip())
    return ", ".join(cleaned)


def quote_ident_mysql(name: str) -> str:
    """MySQL 反引号包裹（先 sanitize 再调用）"""
    n = assert_safe_identifier(name)
    return f"`{n}`"


def quote_ident_ansi(name: str) -> str:
    """ANSI/PG/SQLite 双引号包裹"""
    n = assert_safe_identifier(name)
    return f'"{n}"'


def reject_if_sql_injection_payload(value: str, *, field: str = "value") -> str:
    """
    对“本不该是 SQL 的用户输入”做额外拒绝（辅助层，不能替代 %s 绑定）。
    注意：正常业务文本里也可能含引号，故默认只用于标识符/排序/限制性字段。
    """
    if value is None:
        return value
    text = str(value)
    if _DANGEROUS_SQL_RE.search(text):
        raise SafeNameError(f"检测到可疑 SQL 片段，已拒绝 {field}: {text!r}")
    return text


# ----------------- QueryWrapper 友好封装 -----------------

class ColumnGuard:
    """
    给某个表绑定列白名单，Query 里 eq/order_by 时统一走它。

    用法:
        guard = ColumnGuard(["id", "name", "status", "created_at"])
        col = guard.check("status")
        order = guard.order_by("created_at DESC")
    """

    def __init__(self, columns: Iterable[str], *, table: Optional[str] = None):
        self.table = table
        self.columns: Set[str] = {str(c).strip() for c in columns}

    def check(self, column: str) -> str:
        return assert_in_whitelist(column, self.columns, what="column")

    def order_by(self, expr: str) -> str:
        return sanitize_order_by(expr, self.columns)

    def select_list(self, cols: Sequence[str]) -> str:
        safe = sanitize_columns(cols, self.columns)
        return ", ".join(safe)