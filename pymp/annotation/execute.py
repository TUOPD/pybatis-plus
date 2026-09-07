# -*- coding: utf-8 -*-
"""
@execute —— 通用写操作注解基座
职责：
1. 反射提取 Python 方法入参
2. 渲染 #{param} 为数据库占位符 (%s)
3. 托管给 Executor 执行写操作
"""
import functools
import inspect
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from pymp.core.config import global_config
from pymp.executor.executor import Executor
from pymp.sql import render_sql
from pymp.utils.reflect import merge_func_result

# 匹配 #{param_name}
_SQL_PARAM_PATTERN = re.compile(r"#\{(\w+)\}")

# 动态 SQL 标签：<if test=...> / <foreach ...>
_DYNAMIC_TAG_RE = re.compile(r"<\s*(?:if|foreach)\b", re.IGNORECASE)

def get_executor_for_instance(instance: Any) -> Executor:
    """优先用 Mapper.get_connection，否则走全局 context"""
    provider = getattr(instance, "get_connection", None)
    return Executor(provider if callable(provider) else None)


def render_annotation_sql(
    sql_template: str,
    params: Dict[str, Any],
    *,
    placeholder: Optional[str] = None,
) -> Tuple[str, List[Any]]:
    """渲染注解 SQL：模板含 <if>/<foreach> 时自动走动态 SQL，否则走普通 #{} 渲染。

    用法: @select/@insert/@update/@delete 里的模板都可以直接写
      <if test="name != None"> AND name LIKE #{name}</if>
      <foreach collection="ids" item="id" open=" AND id IN (" separator="," close=")">
          #{id}
      </foreach>
    """
    if _DYNAMIC_TAG_RE.search(sql_template):
        from pymp.sql.dynamic import render_dynamic
        return render_dynamic(sql_template, params)
    return render_sql(sql_template, params, placeholder=placeholder)


def execute(sql_template: str):
    """通用写注解，返回影响行数 (rowcount)（也支持动态 SQL 标签）"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # ✅ 改动点：用 utils.reflect，不再自己 inspect
            params = merge_func_result(func, self, args, kwargs)
            # merge_func_result = bind_args + 执行原函数 + 合并 return dict

            sql, values = render_annotation_sql(sql_template, params)
            # ✅ 改动点：统一走 render_annotation_sql（自动识别动态标签 / ${} / #{}）

            ex = get_executor_for_instance(self)
            return ex.execute(sql, values)

        return wrapper
    return decorator
