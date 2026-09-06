# -*- coding: utf-8 -*-
"""pymp 日志输出中心。

由 global_config 的开关控制，直接输出到控制台(stdout)：
- SQL：show_sql=True 时打印「最终可执行 SQL（占位符已替换为真实值）+ 模板 + 参数」；
- 过程/详情：show_detail=True 时打印事务、插件改写、动态 SQL 等附加日志。

使用独立 logger "pymp"（propagate=False，自带 stdout handler），
避免被宿主框架（如 Flask）默认日志级别过滤掉。
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Optional

_LOGGER_NAME = "pymp"
_configured = False


def _logger() -> logging.Logger:
    global _configured
    if not _configured:
        lg = logging.getLogger(_LOGGER_NAME)
        lg.setLevel(logging.DEBUG)
        lg.propagate = False
        has_stdout = any(
            isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
            for h in lg.handlers
        )
        if not has_stdout:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s | %(message)s", "%H:%M:%S")
            )
            lg.addHandler(handler)
        _configured = True
    return logging.getLogger(_LOGGER_NAME)


def sql(
    sql_text: str,
    *,
    template: Optional[str] = None,
    params: Any = None,
    force: bool = False,
) -> None:
    """打印最终可执行 SQL（占位符已替换为真实值），受 global_config.show_sql 控制。"""
    from pymp.core.config import global_config
    if not (force or global_config.show_sql):
        return
    lines = ["🚀 [SQL] " + sql_text]
    if template:
        lines.append("      模板: " + template)
    if params:
        if isinstance(params, (list, tuple)):
            rendered = repr(list(params))
        else:
            rendered = repr(params)
        lines.append("      参数: " + rendered)
    _logger().info("\n".join(lines))


def detail(msg: str, *args: Any) -> None:
    """过程日志（事务/插件改写/动态 SQL 等），受 global_config.show_detail 控制。"""
    from pymp.core.config import global_config
    if global_config.show_detail:
        _logger().info(msg, *args)


def debug(msg: str, *args: Any) -> None:
    """更细的调试日志，受 global_config.show_detail 控制。"""
    from pymp.core.config import global_config
    if global_config.show_detail:
        _logger().debug(msg, *args)


def info(msg: str, *args: Any) -> None:
    """始终输出（不受开关控制），用于框架启动等重要提示。"""
    _logger().info(msg, *args)


def warning(msg: str, *args: Any) -> None:
    _logger().warning(msg, *args)
