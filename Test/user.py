# -*- coding: utf-8 -*-
from typing import Optional

from pymp.model import BaseModel, TableId, TableName


@TableName("user")
class User(BaseModel):
    """user 表模型（字段与列名一一对应，含 camelCase 列）"""
    id: Optional[int] = TableId()
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    manTest: Optional[str] = None
    imgurl: Optional[str] = None
    delete: Optional[int] = 0
    is_deleted: Optional[int] = None   # 逻辑删除标记（注册 LogicDelete 插件后使用）
    version: Optional[int] = None      # 乐观锁版本号（注册 OptimisticLock 插件后使用）
    tenant_id: Optional[int] = None    # 租户 ID（注册 Tenant 插件后使用）
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None