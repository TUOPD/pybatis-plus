# -*- coding: utf-8 -*-
"""事务：@transactional 装饰器 / transaction 上下文管理器

原理（修复 Executor 内层每句自动 commit 导致事务失效的问题）：
1. transaction() 取到一条连接后，通过 bind_transaction_connection() 把它绑定到
   当前线程/协程上下文，使事务内的所有 get_connection() / Executor 调用都复用同一连接；
2. Executor 检测到“当前处于事务中”后不再每条语句自动 commit/rollback，
   统一由最外层事务在块结束提交、异常时回滚；
3. 事务结束（仅最外层）把连接归还连接池；支持嵌套（内层只是加入外层事务）。
"""
from __future__ import annotations

import functools
import logging
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional

from pymp.core.context import (
    bind_transaction_connection,
    get_connection,
    in_transaction,
    is_db_connection,
    unbind_transaction_connection,
)
from pymp.core.logger import detail

log = logging.getLogger(__name__)


def _disable_autocommit(conn: Any) -> None:
    """尽力关闭驱动自动提交（PyMySQL 等）。失败静默忽略。"""
    try:
        if callable(getattr(conn, "get_autocommit", None)):
            setattr(conn, "_pymp_prev_autocommit", conn.get_autocommit())
        if callable(getattr(conn, "autocommit", None)):
            conn.autocommit(False)
        elif hasattr(conn, "autocommit"):
            conn.autocommit = False
    except Exception:
        pass


def _restore_autocommit(conn: Any) -> None:
    try:
        prev = getattr(conn, "_pymp_prev_autocommit", None)
        if prev is None:
            return
        if callable(getattr(conn, "autocommit", None)):
            conn.autocommit(bool(prev))
        else:
            conn.autocommit = prev
    except Exception:
        pass
    finally:
        try:
            if hasattr(conn, "_pymp_prev_autocommit"):
                del conn._pymp_prev_autocommit
        except Exception:
            pass


@contextmanager
def transaction(
    conn_provider: Optional[Callable[[], Any]] = None,
) -> Generator[Any, None, None]:
    """开启一个数据库事务。

    用法:
        with transaction():                    # 使用全局连接提供者
        with transaction(self.get_connection): # 显式提供取连接函数
        with transaction(conn):                # 直接传连接对象（外部管理，不归还）

    事务内所有 Executor / get_connection() 复用同一条连接；
    只有最外层事务负责 commit/rollback 与归还连接。
    """
    # 是否最外层事务（决定谁 commit/rollback/归还连接）
    is_outer = not in_transaction()

    # 取连接（只取一次，事务内复用）
    if is_db_connection(conn_provider):
        conn = conn_provider  # 调用方直接传入的连接对象（外部管理，不归还）
        owned = False
    elif conn_provider is None:
        conn = get_connection()
        owned = True
    elif callable(conn_provider):
        conn = conn_provider()
        owned = True
    else:
        conn = conn_provider
        owned = False

    if is_outer:
        _disable_autocommit(conn)

    detail("[tx] begin (conn=%s)", id(conn))
    tokens = bind_transaction_connection(conn)
    try:
        yield conn
        if is_outer and hasattr(conn, "commit"):
            detail("[tx] commit")
            conn.commit()
    except BaseException:
        if is_outer and hasattr(conn, "rollback"):
            detail("[tx] rollback")
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        unbind_transaction_connection(tokens)
        if is_outer:
            _restore_autocommit(conn)
            # 最外层负责归还连接（PooledDB 需 close 才归还）
            if owned and conn is not None:
                try:
                    conn.close()
                    detail("[tx] connection returned to pool")
                except Exception:
                    pass


def transactional(func: Optional[Callable] = None, *, conn_attr: str = "get_connection"):
    """
    用法:
      @transactional
      def transfer(self, ...):
          ...

      @transactional(conn_attr="get_connection")
      def service_method(self):
          ...
    """
    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            self_obj = args[0] if args else None
            provider = None
            if self_obj is not None and hasattr(self_obj, conn_attr):
                provider = getattr(self_obj, conn_attr)
            with transaction(provider):
                return fn(*args, **kwargs)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator