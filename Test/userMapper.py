# -*- coding: utf-8 -*-
"""完整演示 userMapper
覆盖：BaseMapper 内置 CRUD + 注解式 SQL(@select/@insert/@update/@delete) + QueryWrapper 封装
"""
from __future__ import annotations

from typing import List, Optional

from pymp.annotation import delete, insert, select, update
from pymp.mapper import BaseMapper
from pymp.model import Page

from Test.user import User


class userMapper(BaseMapper):
    # 绑定模型：select 结果自动映射成 User，且 Query 列白名单 = 模型字段
    model_class = User
    # table_name 可省略（会从 @TableName("user") 自动读取），这里显式写出便于理解
    table_name = "user"

    # ------------------------------------------------------------------
    # 1) BaseMapper 内置 CRUD（已继承，无需重复实现）
    #    insert(entity)  -> 返回自增主键
    #    update_by_id(entity) -> 返回受影响行数
    #    select_by_id(pk) -> 返回 User 或 None
    #    这些都在 api.py 里直接调用。
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 2) 注解式 SQL
    # ------------------------------------------------------------------
    @select("SELECT * FROM user WHERE id = #{id}")
    def select_by_id_anno(self, id: int):
        """方法名含 _by_id -> @select 单条分支（dict）"""
        pass

    @select("SELECT * FROM user", one=False)
    def select_all_anno(self) -> List[dict]:
        """方法名含 _all -> @select 多条分支（List[dict]），显式 one=False 更稳"""
        pass

    @select("SELECT * FROM user WHERE username LIKE #{username}", one=False)
    def select_by_username_like(self, username: str) -> List[dict]:
        """模糊查询：传 'zhang%' 或 '%zhang%'（显式 one=False，避免被误判单条）"""
        pass

    @select("SELECT * FROM user ORDER BY ${order_by}", one=False)
    def select_order_anno(self, order_by: str = "id DESC"):
        """${order_by} 为受控字符串替换（只允许列名 + ASC/DESC）"""
        pass

    @insert(
        "INSERT INTO user(username, password, email) "
        "VALUES (#{username}, #{password}, #{email})"
    )
    def insert_anno(self, username: str, password: str, email: str):
        """@insert：返回自增主键 lastrowid"""
        pass

    @update("UPDATE user SET email = #{email} WHERE id = #{id}")
    def update_email_anno(self, id: int, email: str):
        """@update：正常更新，返回受影响行数"""
        pass

    @update("UPDATE user SET email = #{email}")
    def update_email_no_where(self, email: str):
        """@update 演示：没有 WHERE 会在注解层被拦截（防全表更新），不会真正执行"""
        pass

    @delete("DELETE FROM user WHERE id = #{id}")
    def delete_anno(self, id: int):
        """@delete：注册 LogicDelete 插件后，物理 DELETE 会被改写为软删除 UPDATE"""
        pass

    # ------------------------------------------------------------------
    # 3) QueryWrapper 便捷封装
    # ------------------------------------------------------------------
    def query_users(
        self,
        page: int = 1,
        size: int = 10,
        keyword: Optional[str] = None,
        min_id: Optional[int] = None,
    ) -> Page:
        """分页 + 可选条件（演示 eq/gt/like/order_by/page_result 链式）"""
        q = self.query()
        if min_id is not None:
            q = q.gt("id", min_id)
        if keyword:
            q = q.like("username", keyword)
        return q.order_by("id", desc=True).page_result(page, size)