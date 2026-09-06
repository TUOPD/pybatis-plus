# -*- coding: utf-8 -*-
"""pymp.utils —— 工具函数包（命名转换 / SQL 安全 / 反射绑定）"""
from pymp.utils.naming import (
    snake_to_camel,
    camel_to_snake,
    to_pascal,
    to_snake,
    to_camel,
    table_to_class_name,
    class_to_table_name,
    dict_keys_to_camel,
    dict_keys_to_snake,
)
from pymp.utils.safe import (
    SafeNameError,
    is_safe_identifier,
    is_safe_order_by,
    assert_safe_identifier,
    assert_safe_order_by,
    assert_in_whitelist,
    sanitize_column,
    sanitize_columns,
    sanitize_table,
    sanitize_order_by,
    ColumnGuard,
)
from pymp.utils.reflect import (
    bind_params,
    bind_args,
    merge_func_result,
    get_func_arg_names,
)

__all__ = [
    # naming
    "snake_to_camel",
    "camel_to_snake",
    "to_pascal",
    "to_snake",
    "to_camel",
    "table_to_class_name",
    "class_to_table_name",
    "dict_keys_to_camel",
    "dict_keys_to_snake",
    # safe
    "SafeNameError",
    "is_safe_identifier",
    "is_safe_order_by",
    "assert_safe_identifier",
    "assert_safe_order_by",
    "assert_in_whitelist",
    "sanitize_column",
    "sanitize_columns",
    "sanitize_table",
    "sanitize_order_by",
    "ColumnGuard",
    # reflect
    "bind_params",
    "bind_args",
    "merge_func_result",
    "get_func_arg_names",
]
