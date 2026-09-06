# -*- coding: utf-8 -*-
"""
BaseMapper —— 对标 MyBatis-Plus BaseMapper<T>

约定：
- 子类必须设置 table_name
- 子类建议实现 get_connection()；否则走 pymp.core.context.get_connection
- 简单 CRUD 用内置方法；复杂 SQL 用 @select/@insert/... 写在子类方法上
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from pymp.core import context
from pymp.executor import Executor

log = logging.getLogger(__name__)

# pymp/mapper/base.py（关键部分）
from pymp.core.config import global_config
from pymp.model.field import inspect_table_meta
from pymp.executor.result import camel_to_snake, model_to_dict

class BaseMapper:
    # 子类只需要挂这个（对标 BaseMapper<T>）
    model_class = None

    # 下面都可以不写，自动推导
    table_name: str = ""
    primary_key: str = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._bootstrap_meta()

    def get_connection(self):
        """
        默认走全局 configure 登记的 provider。
        子类可以覆盖成自己的取连方式。
        """

        return context.get_connection()
    @classmethod
    def _bootstrap_meta(cls):
        """类定义完成时：从 model_class 反射填充 table/pk/columns"""
        if cls is BaseMapper:
            return
        mc = getattr(cls, "model_class", None)
        if mc is None:
            return

        meta = inspect_table_meta(mc)
        # 仅当子类没显式覆盖时自动填
        if not getattr(cls, "table_name", None):
            cls.table_name = meta.table_name
        if not getattr(cls, "primary_key", None):
            cls.primary_key = meta.primary_key or global_config.primary_key
        # 缓存列白名单
        cls._auto_columns = meta.columns()
        cls._table_meta = meta

    @property
    def columns(self):
        """自动列白名单：优先反射，否则空"""
        if getattr(self, "_auto_columns", None):
            return list(self._auto_columns)
        if self.model_class is not None:
            return inspect_table_meta(self.model_class).columns()
        return []

    def query(self):
        from pymp.wrapper.query import Query
        return Query(
            self.get_connection,
            self.table_name or self._resolve_table(),
            whitelist=self.columns or None,
            model_cls=self.model_class,
        )

    def _dialect(self):
        """获取适应当前数据库的方言对象 (MySQL / SQLite 等)"""
        from pymp.core.db_type import resolve_dialect
        try:
            conn = self.get_connection()
            return resolve_dialect(conn)
        except Exception:
            return resolve_dialect(None)

    def _ex(self) -> Executor:
        """获取物理执行器"""
        return Executor(self.get_connection)

    def _resolve_table(self) -> str:
        if self.table_name:
            return self.table_name
        if self.model_class is not None:
            return inspect_table_meta(self.model_class).table_name
        raise ValueError(f"{type(self).__name__} 未设置 model_class 或 table_name")

    def _crud(self):
        from pymp.mapper.methods import CrudMethods
        return CrudMethods(
            self._resolve_table(),
            self.primary_key or global_config.primary_key,
            self._dialect(),
        )

    # ---------------- 实体字段名 -> DB 列名 ----------------
    def _python_to_column_map(self) -> Optional[Dict[str, str]]:
        """把模型 python 字段名映射成真实 DB 列名。
        规则：显式 TableField(col=...) 优先；否则开启驼峰约定时
        （map_underscore_to_camel_case=True）转下划线；其余原样。
        """
        if self.model_class is None:
            return None
        meta = inspect_table_meta(self.model_class)
        mapping: Dict[str, str] = {}
        for py_name, f in meta.fields.items():
            if f.column:
                mapping[py_name] = f.column
            elif global_config.map_underscore_to_camel_case:
                mapping[py_name] = camel_to_snake(py_name)
            else:
                mapping[py_name] = py_name
        return mapping

    def _to_db_columns(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """写路径：把 python 字段名 key 转换为真实 DB 列名 key。"""
        mapping = self._python_to_column_map()
        if not mapping:
            return data
        return {mapping.get(k, k): v for k, v in data.items()}

    # ---- insert 自动：实体/字典都可，自动 to_dict + 去 None + 自动填充插件 ----
    def insert(self, entity):
        is_dict = isinstance(entity, dict)
        data = dict(entity) if is_dict else model_to_dict(entity, exclude_none=True)
        # 插件 before_insert（created_at 等）
        from pymp.plugin.interceptor import global_interceptor_chain
        data = global_interceptor_chain.process_insert(self._resolve_table(), data)
        if not is_dict:
            data = self._to_db_columns(data)  # python 字段名 -> 真实 DB 列名
        sql, params = self._crud().insert(data)
        return self._ex().execute_insert(sql, params)

    def update_by_id(self, entity):
        is_dict = isinstance(entity, dict)
        data = dict(entity) if is_dict else model_to_dict(entity, exclude_none=True)
        from pymp.plugin.interceptor import global_interceptor_chain
        data = global_interceptor_chain.process_update(self._resolve_table(), data)
        if not is_dict:
            data = self._to_db_columns(data)  # python 字段名 -> 真实 DB 列名
        sql, params = self._crud().update_by_id(data)
        return self._ex().execute(sql, params)

    def select_by_id(self, id_value):
        sql, params = self._crud().select_by_id(id_value)
        return self._ex().fetch_one(sql, params, model_cls=self.model_class)