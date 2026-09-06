# -*- coding: utf-8 -*-
"""
统一 SQL 执行器：所有 cursor.execute / fetch / commit 只在这里发生
"""
from __future__ import annotations

from contextlib import contextmanager
import logging
from typing import Any, List, Optional, Sequence, Type, TypeVar

from pymp.core.config import global_config
from pymp.core.context import (
    get_connection,
    get_transaction_connection,
    in_transaction,
    is_db_connection,
)
from pymp.core.exceptions import DuplicateKeyError, SqlExecutionError
from pymp.executor.result import map_result, rows_to_dicts

log = logging.getLogger(__name__)
T = TypeVar("T")


class Executor:
    """
    用法:
        ex = Executor()                          # 用全局 get_connection
        ex = Executor(conn_provider=self.get_connection)

        rows = ex.fetch_all(sql, params)
        one  = ex.fetch_one(sql, params)
        n    = ex.execute(sql, params)
        id_  = ex.execute_insert(sql, params)
    """

    def __init__(self, conn_provider=None):
        """
        conn_provider:
          - None: 使用 pymp.core.context.get_connection
          - callable: 无参可调用，返回 connection
          - connection 对象: 直接使用（高级/测试）
        """
        self._conn_provider = conn_provider

    # ------------------------------------------------------------------
    # 连接 & cursor
    # ------------------------------------------------------------------
    def get_conn(self):
        provider = self._conn_provider
        if is_db_connection(provider):
            # 外部直接传入的连接对象（sqlite3/PyMySQL 等）
            conn = provider
        elif callable(provider) or provider is None:
            conn = provider() if callable(provider) else get_connection()
        else:
            conn = provider

        # 首次拿连接时，顺便触发方言自动推断与占位符刷新
        from pymp.core.db_type import resolve_db_type
        resolve_db_type(conn)

        return conn

    @contextmanager
    def _connection(self):
        """获取连接，并保证用后归还/关闭（防止连接池泄漏）。

        所有权规则：
        - 通过 callable provider 或全局 get_connection() 取得的连接，
          视为 Executor“自有”，退出时 close() 归还给连接池（PooledDB 必须 close 才会归还）；
        - 调用方直接传入的连接对象（高级/测试）视为外部连接，Executor 不负责关闭。
        """
        provider = self._conn_provider
        if is_db_connection(provider):
            # 外部直接传入的连接对象 -> 不负责关闭/归还
            conn = provider
            owned = False
        elif callable(provider) or provider is None:
            conn = self.get_conn()
            owned = True
        else:
            conn = provider
            owned = False

        # 当前处于活动事务且取到的正是事务绑定连接 -> 不归还，
        # 由最外层事务统一 commit/rollback 后再归还连接池
        if owned and in_transaction() and conn is get_transaction_connection():
            owned = False

        try:
            yield conn
        finally:
            if owned and conn is not None:
                try:
                    conn.close()
                except Exception:
                    # 归还/关闭失败（如连接已断）不阻断业务，交给连接池自愈
                    pass

    def _cursor(self, conn):
        """尽量拿 dict cursor；拿不到就普通 cursor，稍后 rows_to_dicts 转换"""
        # PyMySQL
        try:
            import pymysql
            return conn.cursor(pymysql.cursors.DictCursor)
        except Exception:
            pass
        # mysql-connector
        try:
            return conn.cursor(dictionary=True)
        except Exception:
            pass
        # psycopg2 RealDictCursor（可选）
        try:
            import psycopg2.extras
            return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        except Exception:
            pass
        return conn.cursor()

    def _format_executable_sql(self, sql: str, params=None) -> str:
        """把占位符换成真实值，方便复制到客户端调试（仅用于打印，不用于真正执行）"""
        if not params:
            return sql

        # 同时兼容 MySQL 的 %s 和 SQLite 的 ?
        # 注意：真正执行仍用原 sql + params，这里只做展示
        formatted = sql
        for p in params:
            if p is None:
                val = "NULL"
            elif isinstance(p, bool):
                val = "1" if p else "0"
            elif isinstance(p, (int, float)):
                val = str(p)
            else:
                safe = str(p).replace("'", "''")
                val = f"'{safe}'"

            if "%s" in formatted:
                formatted = formatted.replace("%s", val, 1)
            elif "?" in formatted:
                formatted = formatted.replace("?", val, 1)
            else:
                break
        return formatted
    def _log_sql(self, sql: str, params: Optional[Sequence[Any]]):
        """打印 SQL 日志：最终可执行 SQL(占位符已替换) + 模板 + 参数。
        受 global_config.show_sql 控制，输出到控制台。"""
        if global_config.show_sql:
            from pymp.core.logger import sql as log_sql
            executable_sql = self._format_executable_sql(sql, params)
            log_sql(executable_sql, template=sql, params=params)

    def _wrap_error(self, e: Exception, sql: str, params: Any) -> Exception:
        msg = str(e).lower()
        # 重复键粗识别（MySQL 1062 / PG unique / sqlite）
        if any(k in msg for k in ("duplicate", "unique constraint", "1062")):
            return DuplicateKeyError(f"{e}\nSQL: {sql}\nparams: {params}")
        return SqlExecutionError(f"{e}\nSQL: {sql}\nparams: {params}")

    def _intercept(self, sql: str, params: Any) -> Any:
        """SQL 执行前统一经过全局插件链（逻辑删除/多租户/乐观锁/防全表攻击等）。
        仅当注册了拦截器时才有开销。
        """
        from pymp.plugin.interceptor import global_interceptor_chain
        if global_interceptor_chain.has_interceptors():
            sql, params = global_interceptor_chain.process_execute(
                sql, list(params or [])
            )
        return sql, params

    def _columns(self, cur) -> Optional[List[str]]:
        if not getattr(cur, "description", None):
            return None
        return [d[0] for d in cur.description]

    # ------------------------------------------------------------------
    # 读
    # ------------------------------------------------------------------
    def fetch_all(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
        *,
        model_cls: Optional[Type[T]] = None,
    ) -> List[Any]:
        with self._connection() as conn:
            sql, params = self._intercept(sql, params)
            cur = self._cursor(conn)
            try:
                self._log_sql(sql, params)
                cur.execute(sql, params or [])
                raw = cur.fetchall() or []
                cols = self._columns(cur)
                rows = rows_to_dicts(raw, cols)
                return map_result(rows, model_cls=model_cls, one=False)
            except Exception as e:
                raise self._wrap_error(e, sql, params) from e
            finally:
                cur.close()

    def fetch_one(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
        *,
        model_cls: Optional[Type[T]] = None,
    ) -> Any:
        # 不强制改 SQL；由调用方 LIMIT 1，或这里直接 fetch 后取第一条
        rows = self.fetch_all(sql, params, model_cls=None)
        return map_result(rows, model_cls=model_cls, one=True)

    def fetch_scalar(self, sql: str, params: Optional[Sequence[Any]] = None) -> Any:
        """取第一行第一列，如 COUNT(1)"""
        row = self.fetch_one(sql, params, model_cls=None)
        if row is None:
            return None
        if isinstance(row, dict):
            # 常见 count 别名
            for key in ("cnt", "count", "total", "COUNT(1)", "count(1)"):
                if key in row:
                    return row[key]
            # 否则取第一个 value
            return next(iter(row.values()), None)
        return row

    # ------------------------------------------------------------------
    # 写
    # ------------------------------------------------------------------
    def execute(self, sql: str, params: Optional[Sequence[Any]] = None) -> int:
        """UPDATE/DELETE/通用写，返回 rowcount。
        处于事务中时不做自动 commit/rollback，交由外层事务统一处理。"""
        with self._connection() as conn:
            sql, params = self._intercept(sql, params)
            cur = self._cursor(conn)
            try:
                self._log_sql(sql, params)
                cur.execute(sql, params or [])
                if not in_transaction() and hasattr(conn, "commit"):
                    conn.commit()
                return cur.rowcount
            except Exception as e:
                if not in_transaction() and hasattr(conn, "rollback"):
                    conn.rollback()
                raise self._wrap_error(e, sql, params) from e
            finally:
                cur.close()

    def execute_insert(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
        *,
        return_id: bool = True,
    ) -> int:
        """
        INSERT:
          return_id=True  -> lastrowid（没有则退回 rowcount）
          return_id=False -> rowcount
        """
        with self._connection() as conn:
            sql, params = self._intercept(sql, params)
            cur = self._cursor(conn)
            try:
                self._log_sql(sql, params)
                cur.execute(sql, params or [])
                if not in_transaction() and hasattr(conn, "commit"):
                    conn.commit()
                if return_id:
                    last_id = getattr(cur, "lastrowid", None)
                    if last_id:
                        return int(last_id)
                return cur.rowcount
            except Exception as e:
                if not in_transaction() and hasattr(conn, "rollback"):
                    conn.rollback()
                raise self._wrap_error(e, sql, params) from e
            finally:
                cur.close()

    def executemany(self, sql: str, params_seq: Sequence[Sequence[Any]]) -> int:
        """批量执行，返回 rowcount（驱动相关，可能不精确）。
        处于事务中时不做自动 commit/rollback，交由外层事务统一处理。"""
        with self._connection() as conn:
            cur = self._cursor(conn)
            try:
                from pymp.core.logger import detail
                detail("[executor] executemany: %s | batch=%s", sql, len(params_seq))
                cur.executemany(sql, list(params_seq))
                if not in_transaction() and hasattr(conn, "commit"):
                    conn.commit()
                return cur.rowcount
            except Exception as e:
                if not in_transaction() and hasattr(conn, "rollback"):
                    conn.rollback()
                raise self._wrap_error(e, sql, params_seq) from e
            finally:
                cur.close()


# 模块级默认执行器（用全局连接）
default_executor = Executor()