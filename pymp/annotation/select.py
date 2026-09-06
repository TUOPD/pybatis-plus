# -*- coding: utf-8 -*-
"""
@select —— 读操作注解
职责：
1. 提取参数渲染 SQL
2. 判断返回单条 (dict) 还是列表 (List[dict])
3. 调用 Executor.fetch_one() / fetch_all()
"""
import functools
from typing import Callable, Optional, Type, TypeVar

from .execute import render_sql, get_executor_for_instance
from ..utils.reflect import merge_func_result

T = TypeVar("T")


def _is_single_result_method(func_name: str) -> bool:
    name = func_name.lower()
    if any(k in name for k in ["_list", "_all", "_page", "get_all", "get_list", "select_list"]):
        return False
    if name.endswith(("_one", "_by_id", "_detail", "_single")):
        return True
    if name.startswith(("get_one", "find_one", "select_one")):
        return True
    if "_by_" in name and not name.endswith("s"):
        return True
    return False


def select(sql_template: str, *, one: Optional[bool] = None, model_cls: Optional[Type[T]] = None):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # ✅ 旧：
            # params = bind_args(func, self, args, kwargs)
            # extra = func(self, *args, **kwargs)
            # if isinstance(extra, dict): params.update(extra)

            # ✅ 新：一行
            params = merge_func_result(func, self, args, kwargs)

            sql, values = render_sql(sql_template, params)
            ex = get_executor_for_instance(self)

            should_one = one if one is not None else _is_single_result_method(func.__name__)
            if should_one:
                return ex.fetch_one(sql, values, model_cls=model_cls)
            return ex.fetch_all(sql, values, model_cls=model_cls)

        return wrapper
    return decorator