# -*- coding: utf-8 -*-
"""
供 SQL 改写类插件（逻辑删除 / 多租户 / 乐观锁 / 防全表攻击等）共用的工具。

设计取舍：
- 采用“括号/引号感知的顶层关键词扫描”，尽量命中最外层 WHERE / GROUP BY /
  ORDER BY / LIMIT，降低把条件误注入到子查询或字符串字面量里的概率；
- 不做完整 SQL AST 解析，因此对“多语句、复杂 CTE、带别名的多表 UPDATE/DELETE”
  等仍建议在业务层自行处理或交给真实 SQL 解析器。
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# 无 WHERE 时的“前向插入锚点”关键词
_CLAUSE_KEYWORDS = {"group", "order", "limit", "having"}


def scan_top_keywords(sql: str) -> List[Tuple[str, int, int]]:
    """返回 (小写关键词, 起始下标, 结束下标)，仅命中括号外、引号外的顶层内容。"""
    hits: List[Tuple[str, int, int]] = []
    i, n = 0, len(sql)
    depth = 0
    quote: Optional[str] = None
    while i < n:
        ch = sql[i]
        if quote:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            i += 1
            continue
        if depth == 0 and (ch.isalpha() or ch == "_"):
            m = _WORD_RE.match(sql, i)
            if m:
                hits.append((m.group(0).lower(), m.start(), m.end()))
                i = m.end()
                continue
        i += 1
    return hits


def statement_type(sql: str) -> Optional[str]:
    """识别语句首关键字: select/update/delete/insert；无法识别返回 None。"""
    m = re.match(r"\s*(SELECT|UPDATE|DELETE|INSERT)\b", sql, re.IGNORECASE)
    return m.group(1).lower() if m else None


def find_top(sql: str, *words: str) -> Optional[int]:
    """返回 sql 中第一个顶层指定关键词的起始下标；找不到返回 None。"""
    for kw, start, _ in scan_top_keywords(sql):
        if kw in words:
            return start
    return None


def _top_where_end(sql: str, where_start: int) -> int:
    """WHERE 子句的结尾：到下一个顶层 group/order/limit/having，或到结尾。"""
    end = len(sql)
    for kw, start, _ in scan_top_keywords(sql):
        if start > where_start and kw in _CLAUSE_KEYWORDS:
            end = min(end, start)
    return end


def filters_column(sql: str, column: str) -> bool:
    """顶层 WHERE/HAVING 段是否已引用 column（用户已显式过滤时避免重复注入）。

    注意：只检查最外层过滤段，投影/子查询里出现该列不会算作“已过滤”。
    """
    pattern = re.compile(rf"\b{re.escape(column)}\b", re.IGNORECASE)
    where_start = find_top(sql, "where", "having")
    if where_start is None:
        return False
    seg = sql[where_start:_top_where_end(sql, where_start)]
    return bool(pattern.search(seg))


def inject_where_condition(
    sql: str,
    condition: str,
    placeholder: str = "%s",
) -> Tuple[str, int]:
    """把 condition（不含 WHERE 前缀，如 `is_deleted = %s`）注入顶层 WHERE。

    返回 (new_sql, param_index)：
    - 有顶层 WHERE：插到 WHERE 之后、其余条件之前；
    - 无 WHERE：插到顶层 GROUP BY / ORDER BY / LIMIT 之前；都没有则追加到末尾。
    param_index = 新条件占位符之前已有的占位符个数（即新参数应插入的列表下标）。
    """
    stripped = sql.strip()
    where_start = find_top(stripped, "where")
    if where_start is not None:
        pos = where_start + len("where")
        new_sql = stripped[:pos] + " " + condition + " AND" + stripped[pos:]
        return new_sql, stripped[:pos].count(placeholder)

    insert_at = len(stripped)
    for kw, start, _ in scan_top_keywords(stripped):
        if kw in _CLAUSE_KEYWORDS:
            insert_at = min(insert_at, start)
    new_sql = stripped[:insert_at] + " WHERE " + condition + " " + stripped[insert_at:]
    return new_sql, stripped[:insert_at].count(placeholder)
