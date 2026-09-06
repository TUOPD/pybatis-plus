# -*- coding: utf-8 -*-
"""
简单 Mapper 注册表（可选）
场景：按表名/名字获取 mapper 实例，或做启动扫描
"""
from __future__ import annotations

from typing import Dict, Type, TypeVar

from pymp.mapper.base import BaseMapper

T = TypeVar("T", bound=BaseMapper)

_REGISTRY: Dict[str, Type[BaseMapper]] = {}


def register_mapper(name: str | None = None):
    """
    装饰器:
      @register_mapper("instance")
      class InstanceMapper(BaseMapper):
          table_name = "instances"
    """
    def deco(cls: Type[T]) -> Type[T]:
        key = name or cls.__name__
        _REGISTRY[key] = cls
        return cls
    return deco


def get_mapper_cls(name: str) -> Type[BaseMapper]:
    if name not in _REGISTRY:
        raise KeyError(f"Mapper 未注册: {name}")
    return _REGISTRY[name]


def create_mapper(name: str) -> BaseMapper:
    return get_mapper_cls(name)()


def all_mappers() -> Dict[str, Type[BaseMapper]]:
    return dict(_REGISTRY)