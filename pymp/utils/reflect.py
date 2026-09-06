# -*- coding: utf-8 -*-
"""
反射工具：函数签名绑定、去掉 self、合并 return dict 等
供 annotation / BaseMapper 复用，避免各处复制 inspect 代码
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Optional, Tuple


def bind_params(
    func: Callable,
    args: tuple,
    kwargs: dict,
    *,
    instance: Any = None,
    drop_self: bool = True,
) -> Dict[str, Any]:
    """
    将调用实参绑定到函数形参名。

    两种用法:
      1) 装饰器内已有 self:
         bind_params(func, args, kwargs, instance=self)
         # 等价于 bind(self, *args, **kwargs)

      2) 已包含 self 的完整 args:
         bind_params(func, (self, *args), kwargs)
    """
    sig = inspect.signature(func)

    if instance is not None:
        bound = sig.bind(instance, *args, **kwargs)
    else:
        bound = sig.bind(*args, **kwargs)

    bound.apply_defaults()
    params = dict(bound.arguments)

    if drop_self:
        params.pop("self", None)
        params.pop("cls", None)

    return params


def bind_args(func: Callable, instance: Any, args: tuple, kwargs: dict) -> Dict[str, Any]:
    """
    annotation 常用短名（与旧代码兼容）:
      bind_args(func, self, args, kwargs) -> {形参名: 值}
    """
    return bind_params(func, args, kwargs, instance=instance, drop_self=True)


def merge_func_result(
    func: Callable,
    instance: Any,
    args: tuple,
    kwargs: dict,
    *,
    call_func: bool = True,
) -> Dict[str, Any]:
    """
    1) 绑定方法入参
    2) 可选执行原函数；若 return dict，则合并进 params

    用途：@select/@execute 里既要入参，又允许方法体 return {"extra": 1}
    """
    params = bind_args(func, instance, args, kwargs)
    if not call_func:
        return params

    extra = func(instance, *args, **kwargs)
    if isinstance(extra, dict):
        params.update(extra)
    return params


def get_func_arg_names(func: Callable, *, skip_self: bool = True) -> Tuple[str, ...]:
    """获取函数形参名列表"""
    sig = inspect.signature(func)
    names = []
    for name, param in sig.parameters.items():
        if skip_self and name in ("self", "cls"):
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        names.append(name)
    return tuple(names)


def has_var_kwargs(func: Callable) -> bool:
    """是否有 **kwargs"""
    for p in inspect.signature(func).parameters.values():
        if p.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    return False


def is_bound_method(func: Callable) -> bool:
    return inspect.ismethod(func)


def get_optional_self(args: tuple) -> Tuple[Optional[Any], tuple]:
    """
    从 args 里尝试拆出 self（用于既支持函数又支持方法的工具）。
    返回 (self_or_none, remaining_args)
    """
    if not args:
        return None, ()
    first = args[0]
    # 粗略判断：实例对象且有 class
    if hasattr(first, "__class__") and not isinstance(first, (str, bytes, dict, list, tuple, int, float, bool)):
        return first, args[1:]
    return None, args


def call_with_optional_dict_return(
    func: Callable,
    instance: Any,
    args: tuple,
    kwargs: dict,
) -> Tuple[Dict[str, Any], Any]:
    """
    执行函数并返回 (合并后的 params, 原始返回值)
    原始返回值不是 dict 时，不合并，原样带回（少数场景需要）
    """
    params = bind_args(func, instance, args, kwargs)
    result = func(instance, *args, **kwargs)
    if isinstance(result, dict):
        params = {**params, **result}
    return params, result