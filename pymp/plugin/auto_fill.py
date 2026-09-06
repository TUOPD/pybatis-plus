# -*- coding: utf-8 -*-
"""
自动填充插件：在 insert/update 时自动给 created_at, updated_at 等字段赋值
"""
from datetime import datetime
from typing import Any, Dict
from pymp.plugin.interceptor import Interceptor


class AutoFillInterceptor(Interceptor):
    def __init__(
        self,
        create_time_field: str = "created_at",
        update_time_field: str = "updated_at",
    ):
        self.create_time_field = create_time_field
        self.update_time_field = update_time_field

    def _now(self):
        # 默认使用标准的 YYYY-MM-DD HH:MM:SS 字符串，亦可改为 datetime.now()
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def before_insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        now_val = self._now()
        # 插入时自动补齐 created_at 和 updated_at
        if self.create_time_field and self.create_time_field not in data:
            data[self.create_time_field] = now_val
        if self.update_time_field and self.update_time_field not in data:
            data[self.update_time_field] = now_val
        return data

    def before_update(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        # 更新时自动刷新 updated_at
        if self.update_time_field:
            data[self.update_time_field] = self._now()
        return data