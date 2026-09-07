# -*- coding: utf-8 -*-
import functools
import re
from typing import Callable

from pymp.annotation.execute import get_executor_for_instance, render_annotation_sql as render_sql
from pymp.core.exceptions import SqlExecutionError
from pymp.utils.reflect import merge_func_result  # ✅

_WHERE_RE = re.compile(r"\bwhere\b", re.IGNORECASE)


def delete(sql_template: str, *, allow_empty_where: bool = False):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            params = merge_func_result(func, self, args, kwargs)  # ✅
            sql, values = render_sql(sql_template, params)

            if not allow_empty_where and not _WHERE_RE.search(sql):
                raise SqlExecutionError(
                    "@delete 拒绝执行没有 WHERE 的 SQL。"
                    "确需全表删除请传 allow_empty_where=True"
                )

            return get_executor_for_instance(self).execute(sql, values)
        return wrapper
    return decorator