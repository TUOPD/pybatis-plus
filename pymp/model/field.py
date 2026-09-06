# -*- coding: utf-8 -*-
"""
字段/表元信息 —— 对标 @TableName / @TableId / @TableLogic / @TableField
轻量实现：用类属性描述，不引入 ORM
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type


@dataclass
class Field:
    """列定义"""
    name: str                          # Python 属性名，如 instance_id
    column: Optional[str] = None       # DB 列名，默认=name
    primary_key: bool = False
    logic_delete: bool = False
    fill_on_insert: Optional[str] = None   # "created_at" 策略名/标记
    fill_on_update: Optional[str] = None
    exist: bool = True                 # False 表示非表字段（仅内存）

    def col(self) -> str:
        return self.column or self.name


@dataclass
class TableMeta:
    table_name: str
    primary_key: str = "id"
    logic_delete_column: Optional[str] = None
    fields: Dict[str, Field] = field(default_factory=dict)

    def columns(self, *, include_pk: bool = True) -> List[str]:
        cols = []
        for f in self.fields.values():
            if not f.exist:
                continue
            if not include_pk and f.primary_key:
                continue
            cols.append(f.col())
        return cols


# --------- 装饰器/描述符风格（可选）---------

def TableName(name: str):
    """
    @TableName("instances")
    class Instance(BaseModel): ...
    """
    def deco(cls: Type):
        cls.__table_name__ = name
        return cls
    return deco


def TableId(column: Optional[str] = None):
    """
    class Instance(BaseModel):
        instance_id: str = TableId("instance_id")
    简化：这里返回 default 占位，真正收集在 BaseModel.__init_subclass__
    """
    return Field(name="", column=column, primary_key=True)


def TableLogic(column: Optional[str] = None):
    return Field(name="", column=column, logic_delete=True)


def TableField(
    column: Optional[str] = None,
    *,
    exist: bool = True,
    fill_on_insert: Optional[str] = None,
    fill_on_update: Optional[str] = None,
):
    return Field(
        name="",
        column=column,
        exist=exist,
        fill_on_insert=fill_on_insert,
        fill_on_update=fill_on_update,
    )


def inspect_table_meta(model_cls: Type) -> TableMeta:
    """从模型类提取表元信息"""
    table = getattr(model_cls, "__table_name__", None) or getattr(model_cls, "table_name", None)
    if not table:
        # 默认类名转下划线复数前：简单用类名小写
        table = model_cls.__name__.lower()

    fields: Dict[str, Field] = {}
    pk = "id"
    logic_col = None

    # 1) 显式 __fields_meta__
    explicit = getattr(model_cls, "__fields_meta__", None)
    if isinstance(explicit, dict):
        for k, f in explicit.items():
            if isinstance(f, Field):
                f.name = f.name or k
                fields[k] = f
                if f.primary_key:
                    pk = f.col()
                if f.logic_delete:
                    logic_col = f.col()

    # 2) 注解字段兜底
    annotations = getattr(model_cls, "__annotations__", {}) or {}
    for name in annotations:
        if name.startswith("_"):
            continue
        if name not in fields:
            fields[name] = Field(name=name)

    # 3) 类属性里塞了 Field 对象的情况
    for name, val in list(vars(model_cls).items()):
        if isinstance(val, Field):
            val.name = val.name or name
            fields[name] = val
            if val.primary_key:
                pk = val.col()
            if val.logic_delete:
                logic_col = val.col()

    if not fields and annotations:
        fields = {n: Field(name=n) for n in annotations if not n.startswith("_")}

    return TableMeta(
        table_name=table,
        primary_key=pk,
        logic_delete_column=logic_col,
        fields=fields,
    )