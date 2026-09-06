# app.py
# -*- coding: utf-8 -*-
from flask import Flask, Blueprint
from flask_restx import Api

from Test.api import user_ns
from pymp.core.db_setup import init_pymp_with_pool
from pymp.plugin import (
    AutoFillInterceptor,
    BlockAttackInterceptor,
    global_interceptor_chain,
    LogicDeleteInterceptor,
    OptimisticLockInterceptor,
    TenantInterceptor,
)


def create_app() -> Flask:
    app = Flask(__name__)  # 启动失败直接暴露配置错误
    init_pymp_with_pool(app)

    # ========== 插件注册（顺序即执行顺序，Test/api.py 的各演示接口依赖以下插件） ==========
    global_interceptor_chain.clear()
    # ① 逻辑删除：DELETE 改写为软删除、SELECT 自动 is_deleted=0（表需有 is_deleted 列）
    # ② 自动填充：insert/update 自动补 createdAt/updatedAt（列名与该模型一致）
    global_interceptor_chain.add_interceptor(
        AutoFillInterceptor(create_time_field="createdAt", update_time_field="updatedAt")
    )
    # ③ 乐观锁：version 自增 + 旧版本校验（表需有 version 列）
    global_interceptor_chain.add_interceptor(OptimisticLockInterceptor(version_field="version"))
    # ④ 多租户：TenantContext 内自动拼 tenant_id 条件（表需有 tenant_id 列）
    global_interceptor_chain.add_interceptor(TenantInterceptor(tenant_column="tenant_id"))
    # ⑤ 防全表更新/删除：无 WHERE 的 UPDATE/DELETE 直接拦截
    global_interceptor_chain.add_interceptor(BlockAttackInterceptor())

    # ========== 只挂业务 API ==========
    api_bp = Blueprint("api", __name__, url_prefix="/api")
    api = Api(api_bp, title="pymp Test API", doc="/docs")
    api.add_namespace(user_ns, path="/users")
    app.register_blueprint(api_bp)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080, debug=True)