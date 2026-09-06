# pymp/core/bootstrap.py
# -*- coding: utf-8 -*-
"""
一站式启动引导
对标 Spring Boot 全局配置入口
"""
from typing import Any, Callable, Optional
from pymp.core.config import global_config
from pymp.core.context import set_connection_provider
from pymp.core.db_type import parse_db_type_from_url, resolve_db_type


def configure(
    *,
    connection_provider: Optional[Callable[[], Any]] = None,
    url: Optional[str] = None,
    db_type: Optional[str] = None,
    show_sql: Optional[bool] = None,
    show_detail: Optional[bool] = None,
    enable_logic_delete: Optional[bool] = None,
    map_underscore_to_camel_case: Optional[bool] = None,
    logic_delete_column: Optional[str] = None,
):
    """
    全局一站式配置入口

    用法 (Flask 项目):
        configure(
            connection_provider=lambda: current_app.instance_db.get_connection(),
            show_sql=True,       # 打印最终可执行 SQL 到控制台
            show_detail=True,    # 额外打印事务/插件改写等过程日志
        )
    """
    if show_sql is not None:
        global_config.show_sql = show_sql
    if show_detail is not None:
        global_config.show_detail = show_detail
    if enable_logic_delete is not None:
        global_config.enable_logic_delete = enable_logic_delete
    if map_underscore_to_camel_case is not None:
        global_config.map_underscore_to_camel_case = map_underscore_to_camel_case
    if logic_delete_column is not None:
        global_config.logic_delete_column = logic_delete_column

    if url:
        global_config.datasource.url = url
        guessed = parse_db_type_from_url(url)
        if guessed:
            global_config._detected_db_type = guessed

    if db_type:
        global_config.db_type = db_type.lower()

    if connection_provider:
        set_connection_provider(connection_provider)