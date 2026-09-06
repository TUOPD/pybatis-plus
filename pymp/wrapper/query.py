# -*- coding: utf-8 -*-
"""
数据查询构造器 Query (对标 MyBatis-Plus 的 QueryWrapper)

职责：
1. 链式拼接 SELECT / WHERE / ORDER BY / LIMIT
2. 列名与表名防注入校验 (utils.safe)
3. 托管给 Executor 执行 fetch_all / fetch_one / fetch_scalar
"""
from __future__ import annotations

from typing import Any, List, Optional, Sequence, Type, TypeVar

from .abstract_wrapper import AbstractWrapper
from pymp.core.db_type import current_placeholder
from pymp.executor.executor import Executor
from pymp.model.page import Page
from pymp.utils.safe import (
    sanitize_column,
    sanitize_columns,
    sanitize_order_by,
    sanitize_table,
)

T = TypeVar("T")


class Query(AbstractWrapper):
    """
    数据查询构造器

    用法:
        Query(conn, "instances") \
            .select("instance_id", "instance_name") \
            .eq("status", 1) \
            .like("instance_name", "仿真") \
            .order_by("created_at", desc=True) \
            .page(1, 10) \
            .list()
    """

    def __init__(
            self,
            connection_provider=None,
            table_name: str = "",
            whitelist: Optional[Sequence[str]] = None,
            model_cls: Optional[Type[T]] = None,
    ):
        super().__init__(placeholder=current_placeholder())
        self._conn_provider = connection_provider
        self._table = sanitize_table(table_name) if table_name else ""
        self._whitelist = whitelist  # 可选的列名白名单集合
        self._model_cls = model_cls  # 可选的接收模型类 (如 InstanceModel)

        # 补全初始化属性
        self._columns: str = "*"
        self._order_by_clause: str = ""
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None

    # ---------------- 链式条件构建 ----------------

    def select(self, *columns: str) -> Query:
        """指定要查询的列，默认 * (自动走安全洗涤)"""
        if columns:
            safe_cols = sanitize_columns(columns, self._whitelist)
            self._columns = ", ".join(safe_cols)
        return self

    def order_by(self, column: str, desc: bool = False) -> Query:
        """排序设置 (自动走安全洗涤)"""
        safe_col = sanitize_column(column, self._whitelist)
        direction = "DESC" if desc else "ASC"
        piece = f"{safe_col} {direction}"

        if not self._order_by_clause:
            self._order_by_clause = f" ORDER BY {piece}"
        else:
            self._order_by_clause += f", {piece}"
        return self

    def page(self, page_no: int, page_size: int) -> Query:
        """设置分页参数 (从第 1 页开始)"""
        self._limit = max(1, page_size)
        self._offset = (max(1, page_no) - 1) * self._limit
        return self

    def limit(self, count: int) -> Query:
        """设置限制条数"""
        self._limit = max(1, count)
        return self

    # ---------------- 覆盖 AbstractWrapper 保证条件列安全 ----------------

    def _add_condition(self, sql_expr: str, value: Any = None, has_val: bool = True):
        """重写底层加条件逻辑：对前面的列名做校验"""
        # 提取表达式开头的列名 (如 "status = %s" -> "status")
        raw_col = sql_expr.split()[0] if sql_expr else ""
        if raw_col and not raw_col.isdigit():
            # 基础安全洗涤 (跳过 1=0 这类硬编码表达式)
            sanitize_column(raw_col, self._whitelist)

        return super()._add_condition(sql_expr, value, has_val=has_val)

    def in_(self, column: str, values: List[Any]) -> "Query":
        """IN 条件：列名同样走安全消毒（白名单/标识符校验），避免漏校验"""
        safe_col = sanitize_column(column, self._whitelist)
        return super().in_(safe_col, values)

    # ---------------- 内部 SQL 构建 ----------------

    def _build_sql(self) -> tuple[str, list]:
        """内部拼接最终 SELECT 语句"""
        if not self._table:
            raise ValueError("Query 缺少 table_name 表名设置！")

        sql = f"SELECT {self._columns} FROM {self._table}"
        if self._wheres:
            sql += " WHERE " + " AND ".join(self._wheres)

        sql += self._order_by_clause

        params = list(self._params)
        ph = self._ph

        if self._limit is not None:
            sql += f" LIMIT {ph}"
            params.append(self._limit)
            if self._offset is not None:
                sql += f" OFFSET {ph}"
                params.append(self._offset)

        return sql, params

    def _get_executor(self) -> Executor:
        """获取执行器"""
        return Executor(self._conn_provider)

    # ---------------- 触发终端执行动作 ----------------

    def list(self) -> List[Any]:
        """执行查询，返回多条记录 (List[dict] 或 List[Model])"""
        sql, params = self._build_sql()
        return self._get_executor().fetch_all(sql, params, model_cls=self._model_cls)

    def one(self) -> Optional[Any]:
        """只返回第一条数据 (自动安全临时拼 LIMIT 1)"""
        old_limit = self._limit
        self._limit = 1

        sql, params = self._build_sql()
        result = self._get_executor().fetch_one(sql, params, model_cls=self._model_cls)

        self._limit = old_limit  # 恢复状态
        return result

    def count(self) -> int:
        """执行 COUNT(1) 统计总行数"""
        old_cols = self._columns
        old_order = self._order_by_clause
        old_limit = self._limit

        # 临时改写为 COUNT
        self._columns = "COUNT(1) AS cnt"
        self._order_by_clause = ""
        self._limit = None

        sql, params = self._build_sql()
        val = self._get_executor().fetch_scalar(sql, params)

        # 恢复原始查询状态
        self._columns = old_cols
        self._order_by_clause = old_order
        self._limit = old_limit

        return int(val) if val is not None else 0

    def page_result(self, page_no: int = 1, page_size: int = 10) -> Page:
        """
        一步到位分页：自动执行 count() 和 list()，并封装为 Page 对象返回
        """
        total = self.count()
        records = self.page(page_no, page_size).list()
        return Page(records=records, total=total, page=page_no, size=page_size)