# -*- coding: utf-8 -*-
"""
pymp 框架自定义异常类体系
作用：细分框架运行中的各类错误，方便配合 Flask 的 @handle_api_errors 进行精准拦截
"""


class MpError(Exception):
    """pymp 框架顶级父类异常，所有框架内部抛出的异常都继承此类"""
    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(self.message)


class ConfigurationError(MpError):
    """框架配置错误异常（例如未设置数据库连接提供者）"""
    pass


class SqlExecutionError(MpError):
    """SQL 语法错误或数据库执行失败异常（如表不存在、字段名拼错）"""
    pass


class DuplicateKeyError(MpError):
    """主键或唯一索引重复异常（如插入了相同的 UUID）"""
    pass


class RecordNotFoundError(MpError):
    """未找到记录异常（Expected 1 record, got 0）"""
    pass


class TooManyResultsError(MpError):
    """查询结果溢出异常（预期返回 1 条记录，但数据库返回了多条）"""
    pass