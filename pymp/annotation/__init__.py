# -*- coding: utf-8 -*-
"""SQL 注解（对标 MyBatis 注解式 SQL）

用法示例:
    class UserMapper(BaseMapper):
        @select("SELECT * FROM user WHERE id = #{id}")
        def select_by_id(self, id): ...

        @insert("INSERT INTO user(name) VALUES (#{name})")
        def insert_user(self, name): ...
"""
from pymp.annotation.execute import execute, get_executor_for_instance
from pymp.annotation.select import select
from pymp.annotation.insert import insert
from pymp.annotation.update import update
from pymp.annotation.delete import delete

__all__ = [
    "select",
    "insert",
    "update",
    "delete",
    "execute",
    "get_executor_for_instance",
]
