# -*- coding: utf-8 -*-
"""
轻量 BaseModel（不是 ORM）
- 当 POJO / 数据结构
- 能 to_dict / from_dict
- 能挂表元信息，供 BaseMapper 选代使用
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Type, TypeVar

from pymp.executor.result import dict_to_model, model_to_dict
from pymp.model.field import Field, TableMeta, inspect_table_meta

T = TypeVar("T", bound="BaseModel")


class BaseModel:
    """
    例:
        @TableName("instances")
        class Instance(BaseModel):
            instance_id: str
            instance_name: str
            status: int = 1
    """
    def __init__(self, **kwargs):
        annotations = getattr(self.__class__, "__annotations__", {}) or {}
        for k in annotations:
            if k in kwargs:
                setattr(self, k, kwargs[k])
            else:
                # 类级默认值是 Field 描述符（TableId()/TableLogic()/TableField() 等）时
                # 视为“未显式赋值”，统一落成 None，避免把 Field 对象带进数据字典
                if isinstance(getattr(self.__class__, k, None), Field):
                    setattr(self, k, None)
                elif not hasattr(self, k):
                    setattr(self, k, None)
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self, exclude_none: bool = False) -> Dict[str, Any]:
        from pymp.executor.result import model_to_dict
        return model_to_dict(self, exclude_none=exclude_none)


    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        return dict_to_model(data or {}, cls)

    @classmethod
    def table_meta(cls) -> TableMeta:
        return inspect_table_meta(cls)

    @classmethod
    def table_name(cls) -> str:
        meta = cls.table_meta()
        return meta.table_name

    def __repr__(self) -> str:
        data = self.to_dict(exclude_none=True)
        body = ", ".join(f"{k}={v!r}" for k, v in list(data.items())[:8])
        return f"{self.__class__.__name__}({body})"