# -*- coding: utf-8 -*-
from typing import Any, List


class AbstractWrapper:
    """封装所有 WHERE 语句的公共逻辑 (eq, like, in, gt...)

    placeholder 通过构造传入，默认 MySQL 的 %s；SQLite 等请传入 "?"。
    Query/UpdateWrapper 会在实例化时根据方言自动填入。
    """

    def __init__(self, placeholder: str = "%s"):
        self._wheres: List[str] = []
        self._params: List[Any] = []
        self._ph = placeholder or "%s"

    def _add_condition(self, sql_expr: str, value: Any = None, has_val: bool = True):
        """核心压栈方法"""
        self._wheres.append(sql_expr)
        if has_val:
            self._params.append(value)
        return self

    def eq(self, column: str, value: Any):
        return self._add_condition(f"{column} = {self._ph}", value)

    def ne(self, column: str, value: Any):
        return self._add_condition(f"{column} <> {self._ph}", value)

    def gt(self, column: str, value: Any):
        return self._add_condition(f"{column} > {self._ph}", value)

    def ge(self, column: str, value: Any):
        return self._add_condition(f"{column} >= {self._ph}", value)

    def lt(self, column: str, value: Any):
        return self._add_condition(f"{column} < {self._ph}", value)

    def like(self, column: str, value: str):
        return self._add_condition(f"{column} LIKE {self._ph}", f"%{value}%")

    def in_(self, column: str, values: List[Any]):
        if not values:
            # 防御性编程：IN 空列表则结果为空
            return self._add_condition("1 = 0", has_val=False)
        placeholders = ", ".join([self._ph] * len(values))
        self._wheres.append(f"{column} IN ({placeholders})")
        self._params.extend(values)
        return self

    def is_null(self, column: str):
        return self._add_condition(f"{column} IS NULL", has_val=False)