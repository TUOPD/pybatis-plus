# -*- coding: utf-8 -*-
"""插件拦截器基类与链式调用
支持 3 个切面钩子 (Hooks):
1. before_insert(data): 插入前处理（如自动填充 created_at）
2. before_update(data): 更新前处理（如自动填充 updated_at, 乐观锁）
3. before_execute(sql, params): SQL 执行前处理（如逻辑删除、多租户、防全表攻击）

说明：before_execute 需在 Executor 真正执行 SQL 之前被调用才会生效，
框架已统一在 pymp.executor.Executor 内部接入 global_interceptor_chain。
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Tuple

log = logging.getLogger(__name__)


class Interceptor:
    """插件基类，子类按需重写对应钩子"""

    def before_insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return data

    def before_update(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return data

    def before_execute(self, sql: str, params: List[Any]) -> Tuple[str, List[Any]]:
        return sql, params


class InterceptorChain:
    """全局插件链管理器（单例模式），线程安全。"""

    def __init__(self):
        self._interceptors: List[Interceptor] = []
        self._lock = threading.Lock()

    def add_interceptor(self, interceptor: Interceptor) -> "InterceptorChain":
        """注册插件（自动去重），返回自身以支持链式调用。"""
        with self._lock:
            if interceptor not in self._interceptors:
                self._interceptors.append(interceptor)
        return self

    def clear(self) -> None:
        """清空全部插件（测试/热重置用）。"""
        with self._lock:
            self._interceptors.clear()

    def has_interceptors(self) -> bool:
        return bool(self._interceptors)

    def _snapshot(self) -> List[Interceptor]:
        with self._lock:
            return list(self._interceptors)

    def process_insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        for plugin in self._snapshot():
            data = plugin.before_insert(table, data)
        return data

    def process_update(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        for plugin in self._snapshot():
            data = plugin.before_update(table, data)
        return data

    def process_execute(self, sql: str, params: List[Any]) -> Tuple[str, List[Any]]:
        for plugin in self._snapshot():
            origin = sql
            sql, params = plugin.before_execute(sql, params)
            if sql != origin:
                # 插件改写了 SQL（逻辑删除/多租户/乐观锁等），show_detail 时打印
                from pymp.core.logger import detail
                detail(
                    "[plugin:%s] SQL 改写\n  旧: %s\n  新: %s",
                    type(plugin).__name__,
                    origin,
                    sql,
                )
        return sql, params


# 全局插件链实例
global_interceptor_chain = InterceptorChain()