# -*- coding: utf-8 -*-
"""
BaseMapper 内置方法对应的 SQL 模板/构建逻辑
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pymp.sql.builder import SqlBuilder
from pymp.sql.dialect import Dialect, MySQLDialect


class CrudMethods:
    """根据 table / pk 生成通用 CRUD 语句"""

    def __init__(self, table: str, pk: str = "id", dialect: Dialect | None = None):
        self.table = table
        self.pk = pk
        self.dialect = dialect or MySQLDialect()

    def _builder(self) -> SqlBuilder:
        return SqlBuilder(self.dialect).table(self.table)

    def select_by_id(self, id_value: Any) -> Tuple[str, List[Any]]:
        b = self._builder().select("*").where(f"{self.pk} = {self.dialect.placeholder}", id_value)
        return b.to_select()

    def select_batch_ids(self, id_list: List[Any]) -> Tuple[str, List[Any]]:
        if not id_list:
            # 永假，避免 IN () 语法错误
            b = self._builder().select("*").where("1 = 0")
            return b.to_select()
        ph = ", ".join([self.dialect.placeholder] * len(id_list))
        b = self._builder().select("*").where(f"{self.pk} IN ({ph})", *id_list)
        return b.to_select()

    def select_all(self) -> Tuple[str, List[Any]]:
        return self._builder().select("*").to_select()

    def insert(self, entity: Dict[str, Any]) -> Tuple[str, List[Any]]:
        return self._builder().to_insert(entity)

    def delete_by_id(self, id_value: Any) -> Tuple[str, List[Any]]:
        b = self._builder().where(f"{self.pk} = {self.dialect.placeholder}", id_value)
        return b.to_delete()

    def delete_batch_ids(self, id_list: List[Any]) -> Tuple[str, List[Any]]:
        if not id_list:
            return f"DELETE FROM {self.table} WHERE 1=0", []
        ph = ", ".join([self.dialect.placeholder] * len(id_list))
        b = self._builder().where(f"{self.pk} IN ({ph})", *id_list)
        return b.to_delete()

    def update_by_id(self, entity: Dict[str, Any]) -> Tuple[str, List[Any]]:
        if self.pk not in entity:
            raise ValueError(f"update_by_id 需要主键字段 {self.pk}")
        data = dict(entity)
        pk_val = data.pop(self.pk)
        if not data:
            raise ValueError("update_by_id 除主键外没有可更新字段")
        b = self._builder()
        for k, v in data.items():
            b.set(k, v)
        b.where(f"{self.pk} = {self.dialect.placeholder}", pk_val)
        return b.to_update()