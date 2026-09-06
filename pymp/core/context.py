# -*- coding: utf-8 -*-
"""
数据库连接与会话上下文管理器
作用：极其优雅地无缝对接 Flask/FastAPI，实现线程/协程隔离的数据库连接提取
"""
import contextvars
from typing import Callable, Any, Optional
from pymp.core.exceptions import ConfigurationError

# ------------------------------------------------------------------------------
# 使用 Python 标准库 contextvars 保证在 Flask 多线程、FastAPI 协程高并发下的连接隔离
# ------------------------------------------------------------------------------
_connection_provider_var: contextvars.ContextVar[Optional[Callable[[], Any]]] = (
    contextvars.ContextVar("_connection_provider_var", default=None)
)

# 全局备用连接提供者
_global_connection_provider: Optional[Callable[[], Any]] = None


def set_connection_provider(provider: Callable[[], Any]) -> None:
    """
    注册全局数据库连接获取闭包/函数
    用法示例 (在 Flask 的 app.py 中)：
        set_connection_provider(lambda: current_app.instance_db.get_connection())
    """
    global _global_connection_provider
    _global_connection_provider = provider


def get_connection() -> Any:
    """
    获取当前上下文中的数据库连接对象
    执行顺序：
      1. 优先从当前线程/协程局部变量获取（支持事务重定向）
      2. 其次调用全局注册的 set_connection_provider 函数获取
      3. 若都未配置，抛出 ConfigurationError
    """
    provider = _connection_provider_var.get() or _global_connection_provider
    if not provider:
        raise ConfigurationError(
            "[pymp] 未配置数据库连接提供者！"
            "请在应用启动时调用 `pymp.set_connection_provider(lambda: ...)` 进行绑定。"
        )
    return provider()


# ------------------------------------------------------------------------------
# 事务状态：当前线程/协程是否处于活动事务，以及事务绑定的那条连接
# 由 pymp.executor.transaction 进入/退出；Executor 据此决定“是否自动提交/归还连接”
# ------------------------------------------------------------------------------
_active_tx_var: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_active_tx_var", default=False
)
_tx_conn_var: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "_tx_conn_var", default=None
)


def in_transaction() -> bool:
    """当前上下文是否处于活动事务中（线程/协程隔离）。"""
    return _active_tx_var.get()


def get_transaction_connection() -> Optional[Any]:
    """返回当前活动事务绑定的连接；不在事务中时返回 None。"""
    return _tx_conn_var.get()


def bind_transaction_connection(conn: Any):
    """把事务连接绑定到当前上下文：
    1. 让事务期间的 get_connection() 都返回这条连接（同事务复用同一连接）；
    2. 标记当前上下文处于事务中。
    返回一组 token，供 unbind_transaction_connection() 恢复。
    """
    token_provider = _connection_provider_var.set(lambda: conn)
    token_active = _active_tx_var.set(True)
    token_conn = _tx_conn_var.set(conn)
    return (token_provider, token_active, token_conn)


def unbind_transaction_connection(tokens) -> None:
    """恢复绑定前的上下文状态（与 bind_transaction_connection 成对调用）。"""
    if not tokens:
        return
    _connection_provider_var.reset(tokens[0])
    _active_tx_var.reset(tokens[1])
    _tx_conn_var.reset(tokens[2])


def is_db_connection(obj: Any) -> bool:
    """判断对象是否为“数据库连接对象”而非“取连接函数/provider”。
    不能用 callable 判断：sqlite3.Connection 等驱动对象自身也可调用，
    需靠 cursor/commit/rollback 特征来识别，避免把连接对象误当 provider 调用。
    """
    return bool(
        obj is not None
        and hasattr(obj, "cursor")
        and hasattr(obj, "commit")
        and hasattr(obj, "rollback")
    )