# -*- coding: utf-8 -*-
"""
命名转换工具：snake_case ↔ camelCase / PascalCase
"""
from __future__ import annotations

import re
from typing import Any, Dict


_RE_CAMEL_1 = re.compile(r"(.)([A-Z][a-z]+)")
_RE_CAMEL_2 = re.compile(r"([a-z0-9])([A-Z])")
_RE_SNAKE_SPLIT = re.compile(r"[_\-\s]+")


def snake_to_camel(name: str, *, upper_first: bool = False) -> str:
    """
    instance_name -> instanceName
    instance_name + upper_first=True -> InstanceName
    """
    if not name:
        return name

    # 已是驼峰且不含下划线，直接处理首字母
    if "_" not in name and "-" not in name and " " not in name:
        if upper_first and name[0].islower():
            return name[0].upper() + name[1:]
        if not upper_first and name[0].isupper() and not name.isupper():
            # PascalCase -> camelCase（仅首字母降）
            return name[0].lower() + name[1:]
        return name

    parts = [p for p in _RE_SNAKE_SPLIT.split(name) if p]
    if not parts:
        return name

    first = parts[0].lower()
    rest = "".join(p[:1].upper() + p[1:].lower() if p else "" for p in parts[1:])
    result = first + rest
    if upper_first and result:
        result = result[0].upper() + result[1:]
    return result


def camel_to_snake(name: str) -> str:
    """
    instanceName -> instance_name
    InstanceName -> instance_name
    HTTPResponse -> http_response（尽力处理连续大写）
    """
    if not name:
        return name
    if "_" in name and name == name.lower():
        return name

    s1 = _RE_CAMEL_1.sub(r"\1_\2", name)
    s2 = _RE_CAMEL_2.sub(r"\1_\2", s1)
    return s2.replace("-", "_").lower()


def to_pascal(name: str) -> str:
    """instance_name / instanceName -> InstanceName"""
    return snake_to_camel(camel_to_snake(name) if not ("_" in name or "-" in name) else name, upper_first=True)


def to_snake(name: str) -> str:
    """任意常见命名 -> snake_case"""
    return camel_to_snake(name)


def to_camel(name: str) -> str:
    """任意常见命名 -> camelCase"""
    if "_" in name or "-" in name or " " in name:
        return snake_to_camel(name, upper_first=False)
    return snake_to_camel(camel_to_snake(name), upper_first=False)


def dict_keys_to_camel(data: Dict[str, Any], *, deep: bool = False) -> Dict[str, Any]:
    """字典 key：下划线 -> 驼峰"""
    out: Dict[str, Any] = {}
    for k, v in (data or {}).items():
        nk = snake_to_camel(str(k))
        if deep and isinstance(v, dict):
            out[nk] = dict_keys_to_camel(v, deep=True)
        elif deep and isinstance(v, list):
            out[nk] = [
                dict_keys_to_camel(i, deep=True) if isinstance(i, dict) else i
                for i in v
            ]
        else:
            out[nk] = v
    return out


def dict_keys_to_snake(data: Dict[str, Any], *, deep: bool = False) -> Dict[str, Any]:
    """字典 key：驼峰 -> 下划线"""
    out: Dict[str, Any] = {}
    for k, v in (data or {}).items():
        nk = camel_to_snake(str(k))
        if deep and isinstance(v, dict):
            out[nk] = dict_keys_to_snake(v, deep=True)
        elif deep and isinstance(v, list):
            out[nk] = [
                dict_keys_to_snake(i, deep=True) if isinstance(i, dict) else i
                for i in v
            ]
        else:
            out[nk] = v
    return out


def table_to_class_name(table_name: str, *, plural_strip: bool = True) -> str:
    """
    instances -> Instance
    sys_user -> SysUser
    """
    name = table_name.strip()
    if plural_strip and name.endswith("s") and not name.endswith("ss"):
        # 极简去复数；复杂英文复数可二期增强
        name = name[:-1]
    return to_pascal(name)


def class_to_table_name(class_name: str, *, plural: bool = False) -> str:
    """Instance -> instance / instances"""
    name = camel_to_snake(class_name)
    if plural and not name.endswith("s"):
        name += "s"
    return name