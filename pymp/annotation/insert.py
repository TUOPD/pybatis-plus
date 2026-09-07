# -*- coding: utf-8 -*-
"""
@insert —— 插入注解
职责：渲染 #{param} 并执行 INSERT，优先返回自增主键 lastrowid；
     没有自增主键时返回受影响行数（rowcount）。
"""
import functools
from typing import Callable

from .execute import get_executor_for_instance, render_annotation_sql as render_sql
from ..utils.reflect import merge_func_result


def insert(sql_template: str, *, return_id: bool = True):
    """
    插入注解 (@insert)

    用法:
        @insert("INSERT INTO user(name) VALUES (#{name})")
        def add(self, name):
            return {"name": name}          # 或方法直接以形参传值

    参数:
        return_id: True 时优先返回 lastrowid，否则返回受影响行数
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            params = merge_func_result(func, self, args, kwargs)
            sql, values = render_sql(sql_template, params)
            ex = get_executor_for_instance(self)
            return ex.execute_insert(sql, values, return_id=return_id)

        return wrapper
    return decorator