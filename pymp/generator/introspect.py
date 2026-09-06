# -*- coding: utf-8 -*-
"""
元数据逆向读取器：查询 MySQL 的 information_schema 读取表结构与字段注释
"""
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class ColumnMeta:
    name: str  # 字段列名，如 instance_name
    db_type: str  # 数据库类型，如 varchar
    is_pk: bool  # 是否为主键
    comment: str  # 字段注释
    py_type: str = "str"  # 映射后的 Python 类型 (str, int, datetime 等)


@dataclass
class TableInfo:
    table_name: str  # 表名，如 instances
    comment: str  # 表注释
    columns: List[ColumnMeta] = field(default_factory=list)

    @property
    def class_name(self) -> str:
        """把 instances / sys_user 转成首字母大写的驼峰类名 Instance / SysUser"""
        name = self.table_name
        if name.endswith("s"):
            name = name[:-1]  # 去掉复数 s
        return "".join(part.capitalize() for part in name.split("_"))


def _db_type_to_py_type(db_type: str) -> str:
    """MySQL 类型 -> Python 类型映射"""
    db_type = db_type.lower()
    if any(k in db_type for k in ["int", "bigint", "tinyint"]):
        return "int"
    if any(k in db_type for k in ["float", "double", "decimal"]):
        return "float"
    if any(k in db_type for k in ["datetime", "timestamp", "date"]):
        return "datetime"
    return "str"


class DbIntrospector:
    """数据库元信息读取器"""

    def __init__(self, conn):
        self.conn = conn

    def get_table_info(self, db_name: str, table_name: str) -> TableInfo:
        cur = self.conn.cursor()
        try:
            # 1. 查表注释
            cur.execute("""
                        SELECT TABLE_COMMENT
                        FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = %s
                          AND TABLE_NAME = %s
                        """, (db_name, table_name))
            row = cur.fetchone()
            table_comment = (row[0] if row else "") or table_name

            # 2. 查字段列表
            cur.execute("""
                        SELECT COLUMN_NAME, DATA_TYPE, COLUMN_KEY, COLUMN_COMMENT
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = %s
                          AND TABLE_NAME = %s
                        ORDER BY ORDINAL_POSITION
                        """, (db_name, table_name))
            cols = cur.fetchall()

            columns = []
            for col_name, data_type, col_key, col_comment in cols:
                columns.append(ColumnMeta(
                    name=col_name,
                    db_type=data_type,
                    is_pk=(col_key == "PRI"),
                    comment=col_comment or "",
                    py_type=_db_type_to_py_type(data_type)
                ))

            return TableInfo(table_name=table_name, comment=table_comment, columns=columns)
        finally:
            cur.close()