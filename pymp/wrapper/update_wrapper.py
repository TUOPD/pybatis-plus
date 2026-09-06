# -*- coding: utf-8 -*-
from .abstract_wrapper import AbstractWrapper
from pymp.core.db_type import current_placeholder


class UpdateWrapper(AbstractWrapper):
    """
    修改构造器
    用法: UpdateWrapper(conn, "user").set("status", 0).eq("id", 1).execute()
    """

    def __init__(self, connection_provider, table_name: str):
        super().__init__(placeholder=current_placeholder())
        self._conn_provider = connection_provider
        self._table = table_name
        self._sets = []
        self._set_params = []

    def set(self, column: str, value: any):
        """设置更新字段 set column = value"""
        self._sets.append(f"{column} = {self._ph}")
        self._set_params.append(value)
        return self

    def execute(self) -> int:
        """执行 UPDATE，返回受影响的行数"""
        if not self._sets:
            raise ValueError("UpdateWrapper 缺少 set() 字段更新设置！")

        sql = f"UPDATE {self._table} SET " + ", ".join(self._sets)

        if self._wheres:
            sql += " WHERE " + " AND ".join(self._wheres)

        # 参数顺序：先 SET 的参数，后 WHERE 的参数
        final_params = self._set_params + self._params

        conn = self._conn_provider()
        cur = conn.cursor()
        try:
            cur.execute(sql, final_params)
            conn.commit()
            return cur.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            # 归还连接（PooledDB 必须 close 才会归还到池，防止连接泄漏）
            try:
                conn.close()
            except Exception:
                pass