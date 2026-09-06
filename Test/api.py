# -*- coding: utf-8 -*-
"""pymp 全功能 REST 测试接口（Flask + flask-restx）

运行前提（见 Test/schema.sql 与 Test/app.py）：
 1. 执行 schema.sql 建好 user 表（含 is_deleted/version/tenant_id 等列）；
 2. app.py 注册了 逻辑删除/自动填充/乐观锁/多租户/防全表 插件。

一键自测清单（浏览器/curl 均可）：
  GET    /api/users?page=1&size=10&keyword=zhang       分页列表
  POST   /api/users       body: {"username":..,"password":..,"email":..}
  GET    /api/users/all                                  注解 @select 多条
  GET    /api/users/<id>                                 内置 select_by_id
  PUT    /api/users/<id>                                 内置 update_by_id
  DELETE /api/users/<id>                                 @delete -> 逻辑删除
  PUT    /api/users/<id>/optimistic  body: {"version": 当前版本}   乐观锁冲突演示
  GET    /api/users/count /order /search /query-demo     QueryWrapper 演示
  POST   /api/users/anno-demo /<id>/email /no-where-demo 注解 @insert/@update/防全表
  POST   /api/users/tx-rollback-demo /tx-commit-demo      事务 回滚/提交
  GET    /api/users/tenant-demo?tid=1                      多租户隔离
"""
from __future__ import annotations

import time

from flask import request
from flask_restx import Namespace, Resource

from pymp import transaction
from pymp.core.exceptions import SqlExecutionError
from pymp.model import Page
from pymp.plugin import TenantContext

from Test.user import User
from Test.userMapper import userMapper

user_ns = Namespace("users", description="用户接口（演示 pymp 全功能）")

mapper = userMapper()


# ---------------------------------------------------------------------------
# 序列化 / 响应工具
# ---------------------------------------------------------------------------
def _dump(obj):
    """模型 / Page / dict / list 统一转成可 JSON 序列化的结构。"""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Page):
        return obj.to_dict()
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_dump(x) for x in obj]
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    return obj


def _ok(data=None, msg="ok"):
    resp = {"code": 0, "msg": msg}
    if data is not None:
        resp["data"] = _dump(data)
    return resp


def _fail(msg, code=400):
    return {"code": code, "msg": msg}, code


def _count():
    return mapper.query().count()


# ===========================================================================
# 1) CRUD（BaseMapper 内置方法 + 逻辑删除/自动填充等插件）
# ===========================================================================
@user_ns.route("")
class UserList(Resource):
    def get(self):
        """分页列表：?page=1&size=10&keyword=zhang&min_id=1"""
        page = int(request.args.get("page", 1) or 1)
        size = min(int(request.args.get("size", 10) or 10), 100)
        keyword = request.args.get("keyword") or None
        min_id = request.args.get("min_id", type=int)
        return _ok(mapper.query_users(page=page, size=size, keyword=keyword, min_id=min_id))

    def post(self):
        """新增用户：body={"username":..,"password":..,"email":..}"""
        body = request.get_json(force=True) or {}
        if not body.get("username"):
            return _fail("username 必填")
        new_id = mapper.insert(User(**body))
        return _ok(mapper.select_by_id(new_id), "created")


@user_ns.route("/all")
class UserAll(Resource):
    def get(self):
        """@select 注解演示：全表（逻辑删除行自动被过滤）"""
        return _ok(mapper.select_all_anno())


@user_ns.route("/count")
class UserCount(Resource):
    def get(self):
        """QueryWrapper count 演示"""
        return _ok({"total": _count()})


@user_ns.route("/order")
class UserOrder(Resource):
    def get(self):
        """${order_by} 受控替换演示：?order_by=createdAt DESC"""
        order_by = request.args.get("order_by", "id DESC")
        return _ok(mapper.select_order_anno(order_by=order_by))


@user_ns.route("/search")
class UserSearch(Resource):
    def get(self):
        """注解模糊查询：?username=zhang%"""
        username = request.args.get("username", "%")
        print(username)
        return _ok(mapper.select_by_username_like(username=username))


@user_ns.route("/query-demo")
class UserQueryDemo(Resource):
    def get(self):
        """QueryWrapper 多条件演示：in_ + gt + is_null + limit"""
        min_id = request.args.get("min_id", type=int) or 0
        demo = {
            "by_ids_in": mapper.query().in_("id", [1, 2, 3]).list(),
            "gt_id_limit": mapper.query().gt("id", min_id).limit(5).list(),
            "email_is_null": mapper.query().is_null("email").list(),
        }
        return _ok(demo)


@user_ns.route("/<int:uid>")
class UserItem(Resource):
    def get(self, uid):
        """内置 select_by_id：返回 User 模型"""
        user = mapper.select_by_id(uid)
        if user is None:
            return _fail("not found", 404)
        return _ok(user)

    def put(self, uid):
        """内置 update_by_id：body 内非空字段覆盖更新"""
        cur = mapper.select_by_id(uid)
        if cur is None:
            return _fail("not found", 404)
        body = request.get_json(force=True) or {}
        merged = cur.to_dict()
        merged.update({k: v for k, v in body.items() if v is not None})
        affected = mapper.update_by_id(User(**merged))
        return _ok({"affected": affected}, "updated")

    def delete(self, uid):
        """@delete 注解：注册 LogicDelete 后这里变为软删除"""
        affected = mapper.delete_anno(uid)
        return _ok({"affected": affected}, "deleted(soft)")


# ===========================================================================
# 2) 乐观锁 / 多租户 / 防全表 / 事务 / 注解 演示
# ===========================================================================
@user_ns.route("/<int:uid>/optimistic")
class UserOptimistic(Resource):
    def put(self, uid):
        """乐观锁：body={"username":"新名","version": <读取时的版本>}
        若提交的 version 已过期（比库中旧）-> affected=0 表示冲突。
        """
        body = request.get_json(force=True) or {}
        cur = mapper.select_by_id(uid)
        if cur is None:
            return _fail("not found", 404)
        cur_version = cur.version if cur.version is not None else 1
        submit_version = int(body.get("version", cur_version))
        updater = User(
            id=uid,
            username=body.get("username") or cur.username,
            email=body.get("email") or cur.email,
            version=submit_version,
        )
        affected = mapper.update_by_id(updater)
        return _ok({
            "affected": affected,
            "conflict": affected == 0,
            "hint": "affected=0 表示 version 已过期(乐观锁冲突，可重查最新数据后重试)",
        })


@user_ns.route("/tenant-demo")
class UserTenantDemo(Resource):
    def get(self):
        """多租户：?tid=1 时 TenantContext 内自动拼 tenant_id = 1；不传则不做隔离"""
        tid = request.args.get("tid", type=int)
        if tid is None:
            return _ok({"hint": "传 ?tid=1 观察多租户自动隔离效果"})
        with TenantContext(tenant_id=tid):
            rows = mapper.query().select("id", "username", "tenant_id").list()
        return _ok({"tenant_id": tid, "rows": rows})


@user_ns.route("/no-where-demo")
class UserNoWhere(Resource):
    def put(self):
        """防全表更新演示：@update 不带 WHERE -> 注解层直接拒绝（不会真正执行）"""
        try:
            mapper.update_email_no_where(email="hacked@example.com")
            return _ok(None, "unexpected: 未拦截！")
        except SqlExecutionError as e:
            return _ok({"blocked": True, "detail": str(e)})


@user_ns.route("/anno-demo")
class UserAnnoInsert(Resource):
    def post(self):
        """@insert 注解演示（与实体 insert 不同的写法）"""
        body = request.get_json(force=True) or {}
        new_id = mapper.insert_anno(
            username=body.get("username", f"anno-{int(time.time())}"),
            password=body.get("password", "123456"),
            email=body.get("email", "anno@demo.com"),
        )
        return _ok({"new_id": new_id})


@user_ns.route("/<int:uid>/email")
class UserEmail(Resource):
    def put(self, uid):
        """@update 注解演示：只改 email"""
        body = request.get_json(force=True) or {}
        email = body.get("email")
        if not email:
            return _fail("email 必填")
        affected = mapper.update_email_anno(id=uid, email=email)
        return _ok({"affected": affected}, "updated")


@user_ns.route("/tx-rollback-demo")
class UserTxRollback(Resource):
    def post(self):
        """事务演示：插入后抛异常 -> 自动回滚，总条数不变"""
        before = _count()
        try:
            with transaction():
                mapper.insert(User(
                    username=f"tx-{int(time.time())}",
                    password="x",
                    email="tx@x.com",
                ))
                raise RuntimeError("模拟业务中途失败")
        except RuntimeError:
            pass
        after = _count()
        return _ok({"before": before, "after": after, "rolled_back": before == after})


@user_ns.route("/tx-commit-demo")
class UserTxCommit(Resource):
    def post(self):
        """事务演示：两条插入全部成功 -> 一次性提交，总条数 +2"""
        before = _count()
        t = int(time.time())
        with transaction():
            mapper.insert(User(username=f"txA-{t}", password="x", email="a@x.com"))
            mapper.insert(User(username=f"txB-{t}", password="x", email="b@x.com"))
        after = _count()
        return _ok({"before": before, "after": after, "committed": after == before + 2})