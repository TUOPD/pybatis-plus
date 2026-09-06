# -*- coding: utf-8 -*-
"""
结果映射：DB 行 → dict / Model
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Type, TypeVar

from pymp.core.config import global_config

T = TypeVar("T")

_SNAKE_1 = re.compile(r"_([a-zA-Z])")


def serialize_value(v: Any) -> Any:
    """辅助函数：处理 JSON 不可序列化的类型 (datetime, date, Decimal 等)"""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, Decimal):
        return float(v)  # 或 str(v)
    return v


def snake_to_camel(name: str) -> str:
    """instance_name -> instanceName"""
    parts = name.split("_")
    if not parts:
        return name
    return parts[0] + "".join(p.title() for p in parts[1:] if p)


def camel_to_snake(name: str) -> str:
    """instanceName -> instance_name"""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def row_to_dict(row: Any, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    把任意行对象转成 dict
    支持: dict / tuple+columns / 带 _mapping 的 Row / 普通对象
    """
    if row is None:
        return {}

    if isinstance(row, dict):
        data = dict(row)
    elif columns is not None and isinstance(row, (tuple, list)):
        data = dict(zip(columns, row))
    elif hasattr(row, "_mapping"):  # SQLAlchemy Row 等
        data = dict(row._mapping)
    elif hasattr(row, "__dict__") and not isinstance(row, type):
        data = {k: v for k, v in vars(row).items() if not k.startswith("_")}
    else:
        # 最后兜底
        data = {"value": row}

    # 1. 驼峰转换
    if global_config.map_underscore_to_camel_case:
        data = {snake_to_camel(k): v for k, v in data.items()}

    # 2. ✅ 修复点：在这里对所有 value 进行序列化清洗 (datetime -> str)
    data = {k: serialize_value(v) for k, v in data.items()}

    return data


def rows_to_dicts(rows: Iterable[Any], columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    return [row_to_dict(r, columns) for r in (rows or [])]


def dict_to_model(data: Dict[str, Any], model_cls: Type[T]) -> T:
    """
    dict → Model
    优先支持:
      - pydantic v2: model_validate
      - dataclass / 普通类: 尝试关键字构造，失败则逐字段 setattr
    """
    if data is None:
        return None  # type: ignore

    # pydantic v2
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)  # type: ignore

    # pydantic v1
    if hasattr(model_cls, "parse_obj"):
        return model_cls.parse_obj(data)  # type: ignore

    try:
        return model_cls(**data)  # type: ignore
    except TypeError:
        obj = model_cls()  # type: ignore
        for k, v in data.items():
            # 兼容 Model 用驼峰字段、DB 用下划线
            if hasattr(obj, k):
                setattr(obj, k, v)
            else:
                camel = snake_to_camel(k)
                if hasattr(obj, camel):
                    setattr(obj, camel, v)
                else:
                    # 宽松：动态挂属性
                    try:
                        setattr(obj, k, v)
                    except Exception:
                        pass
        return obj


def model_to_dict(obj: Any, *, exclude_none: bool = False) -> Dict[str, Any]:
    """Model / 对象 / dict 统一转成字典 dict (过滤下划线开头内部属性)"""
    if obj is None:
        return {}

    if isinstance(obj, dict):
        data = dict(obj)
    elif hasattr(obj, "model_dump"):  # Pydantic v2
        data = obj.model_dump()
    elif hasattr(obj, "dict") and callable(obj.dict):  # Pydantic v1
        data = obj.dict()
    elif hasattr(obj, "__dataclass_fields__"):  # dataclass
        from dataclasses import asdict

        data = asdict(obj)
    else:
        data = {}
        # 1. 优先提取 __annotations__ 里显式定义的类型属性
        if hasattr(obj, "__annotations__"):
            for k in obj.__annotations__:
                if not k.startswith("_") and hasattr(obj, k):
                    data[k] = getattr(obj, k)

        # 2. 提取实例变量 vars(obj)
        if hasattr(obj, "__dict__"):
            for k, v in vars(obj).items():
                if not k.startswith("_") and not callable(v):
                    data[k] = v

    # ✅ 修复点：移到最外层，确保所有分支（dict, pydantic, dataclass等）都会执行序列化清洗
    data = {k: serialize_value(v) for k, v in data.items()}

    # 二道保险：剔除所有下划线开头的 key
    data = {k: v for k, v in data.items() if not str(k).startswith("_")}

    if exclude_none:
        data = {k: v for k, v in data.items() if v is not None}

    return data


def map_result(
    rows: List[Dict[str, Any]],
    *,
    model_cls: Optional[Type[T]] = None,
    one: bool = False,
) -> Any:
    if model_cls is not None:
        models = [dict_to_model(r, model_cls) for r in rows]
        if one:
            return models[0] if models else None
        return models

    if one:
        return rows[0] if rows else None
    return rows