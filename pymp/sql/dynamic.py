# -*- coding: utf-8 -*-
"""
极简动态 SQL（MyBatis <if> / <foreach> 的子集）

支持写法（写在 Python 三引号字符串里）:
  SELECT * FROM t
  WHERE 1=1
  <if test="name"> AND name LIKE #{name} </if>
  <if test="status != None"> AND status = #{status} </if>
  <foreach collection="ids" item="id" open=" AND id IN (" separator="," close=")">
    #{id}
  </foreach>

说明：
- test 表达式是受控的小型 eval（只读 params），不要对用户输入开放 test 字符串
- 复杂动态仍建议在 Python 里 if 拼装，或用 QueryWrapper
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from pymp.sql.renderer import render_sql
from pymp.core.exceptions import SqlExecutionError

_IF_BLOCK = re.compile(
    r"<if\s+test\s*=\s*[\"'](.+?)[\"']\s*>(.*?)</if>",
    re.IGNORECASE | re.DOTALL,
)
_FOREACH_BLOCK = re.compile(
    r"<foreach\s+([^>]+)>(.*?)</foreach>",
    re.IGNORECASE | re.DOTALL,
)
_ATTR = re.compile(r"(\w+)\s*=\s*[\"']([^\"']*)[\"']")


def _eval_test(expr: str, params: Dict[str, Any]) -> bool:
    """极小安全集：允许 params 键名、None、比较、and/or/not"""
    # 把裸标识符变成 params.get('x')
    # 例: name -> params.get('name')
    #     status != None -> params.get('status') != None
    def repl_ident(m: re.Match) -> str:
        token = m.group(0)
        if token in ("None", "True", "False", "and", "or", "not", "in", "is"):
            return token
        if token.isdigit():
            return token
        return f"params.get({token!r})"

    py_expr = re.sub(r"[A-Za-z_][A-Za-z0-9_]*", repl_ident, expr)
    try:
        return bool(eval(py_expr, {"__builtins__": {}}, {"params": params}))  # noqa: S307
    except Exception as e:
        raise SqlExecutionError(f"动态 SQL <if test> 解析失败: {expr!r}, err={e}") from e


def _parse_attrs(attr_text: str) -> Dict[str, str]:
    return {k: v for k, v in _ATTR.findall(attr_text)}


def apply_dynamic(sql_template: str, params: Dict[str, Any]) -> str:
    """先展开 <if> / <foreach>，得到只含 #{} 的普通模板"""

    # 1) foreach
    def foreach_sub(m: re.Match) -> str:
        attrs = _parse_attrs(m.group(1))
        body = m.group(2).strip()
        collection = attrs.get("collection")
        item = attrs.get("item", "item")
        open_ = attrs.get("open", "")
        close = attrs.get("close", "")
        separator = attrs.get("separator", ",")

        if not collection:
            raise SqlExecutionError("<foreach> 缺少 collection")
        data = params.get(collection) or []
        if not isinstance(data, (list, tuple, set)):
            raise SqlExecutionError(f"<foreach collection={collection}> 必须是列表")

        parts: List[str] = []
        # 把每个元素临时放进 params: id_0, id_1 ... 或复用 item 名做多次替换
        for i, val in enumerate(data):
            key = f"__fe_{collection}_{i}"
            params[key] = val
            # body 里的 #{item} -> #{__fe_xxx_i}
            piece = body.replace(f"#{{{item}}}", f"#{{{key}}}")
            parts.append(piece)
        if not parts:
            return ""  # 空集合：整段消失（调用方应自己处理 IN 空）
        return open_ + separator.join(parts) + close

    sql = _FOREACH_BLOCK.sub(foreach_sub, sql_template)

    # 2) if
    def if_sub(m: re.Match) -> str:
        test, body = m.group(1), m.group(2)
        return body if _eval_test(test, params) else ""

    sql = _IF_BLOCK.sub(if_sub, sql)
    return sql


def render_dynamic(sql_template: str, params: Dict[str, Any] | None = None) -> Tuple[str, List[Any]]:
    params = dict(params or {})
    expanded = apply_dynamic(sql_template, params)
    return render_sql(expanded, params)