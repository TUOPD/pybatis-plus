# Pybatis-plus（pymp）

一个轻量、**MyBatis-Plus 风格**的 Python 数据访问框架（非 ORM）。
面向 Flask / FastAPI 等 Web 项目，提供：BaseModel 轻模型、BaseMapper 通用 CRUD、QueryWrapper 链式查询、注解式 SQL、动态 SQL、逻辑删除 / 乐观锁 / 多租户 / 自动填充 / 防全表攻击等插件、以及事务支持。

> 目标：把 Java 端 MyBatis-Plus 的“开发手感”带到 Python，同时保持依赖极轻、SQL 可读、可审计。

---

## 目录

- [特性](#特性)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [环境变量 / .env 变量表](#环境变量--env-变量表)
- [日志系统](#日志系统)
- [模型定义 BaseModel](#模型定义-basemodel)
- [Mapper 与内置 CRUD](#mapper-与内置-crud)
- [QueryWrapper 链式查询](#querywrapper-链式查询)
- [注解式 SQL](#注解式-sql)
- [动态 SQL](#动态-sql)
- [分页 Page](#分页-page)
- [事务 transaction / @transactional](#事务-transaction--transactional)
- [插件机制](#插件机制)
- [连接池与连接管理](#连接池与连接管理)
- [代码生成器](#代码生成器)
- [Test 演示工程](#test-演示工程)
- [已知限制与注意事项](#已知限制与注意事项)

---

## 特性

- **轻量模型**：`BaseModel` 用 `@TableName/@TableId/@TableField/@TableLogic` 描述表结构，支持 `to_dict/from_dict`。
- **通用 Mapper**：`BaseMapper` 内置 `insert / update_by_id / select_by_id`，自动处理字段→列名映射与插件。
- **QueryWrapper**：`eq/ne/gt/ge/lt/like/in_/is_null/order_by/limit/page/count/one/list` 链式构建并安全执行。
- **注解式 SQL**：`@select/@insert/@update/@delete`，`#{name}` 预编译占位符、`${name}` 受控替换（自动安全校验）。
- **动态 SQL 子集**：`<if test>` / `<foreach>`（MyBatis 子集）。
- **插件**（对标 MP InnerInterceptor）：逻辑删除、自动填充、乐观锁、多租户、防全表更新/删除，SQL 改写统一在 `Executor` 执行前生效。
- **事务**：`with transaction():` / `@transactional`，线程/协程上下文绑定同一连接；Executor 不再逐句自动提交。
- **连接安全**：所有 SQL 统一走 `Executor`，用后自动归还连接池；占位符按方言统一（SQLite `?` / MySQL `%s`）。
- **日志**：可按开关打印「最终可执行 SQL（参数已替换）+ 模板 + 参数」及事务/插件改写等过程日志。

---

## 目录结构

```
Pybatis-plus/
├── pymp/                      # 框架源码
│   ├── __init__.py            # 顶层公共 API 导出
│   ├── core/                  # 核心：配置/上下文/方言/异常/日志/连接池
│   │   ├── config.py          #   Configuration / DataSourceConfig / PoolConfig
│   │   ├── bootstrap.py       #   configure() 一站式配置入口
│   │   ├── context.py         #   连接上下文（provider + 事务绑定 + is_db_connection）
│   │   ├── db_type.py         #   方言自动识别 + current_placeholder()
│   │   ├── db_setup.py        #   Flask 连接池初始化（读 .env）
│   │   ├── logger.py          #   pymp 日志输出中心
│   │   ├── constants.py       #   默认常量
│   │   └── exceptions.py      #   异常体系（MpError 等）
│   ├── model/                 # BaseModel / Page / 表元信息
│   ├── mapper/                # BaseMapper / CrudMethods / 注册表
│   ├── wrapper/               # Query / UpdateWrapper（链式条件）
│   ├── sql/                   # SqlBuilder / 方言 / renderer / 动态SQL
│   ├── executor/              # Executor / 结果映射 / 事务
│   ├── plugin/                # 拦截器链 + 各插件
│   ├── annotation/            # @select/@insert/@update/@delete
│   ├── generator/             # CLI 代码生成（MySQL 逆向）
│   └── utils/                 # naming / safe(防注入) / reflect
├── Test/                      # Flask + flask_restx 演示工程
│   ├── app.py                 #   启动：连接池 + 插件注册 + 路由
│   ├── api.py                 #   全功能 REST 测试接口
│   ├── userMapper.py          #   Mapper 演示
│   ├── user.py                #   User 模型
│   ├── schema.sql             #   演示建表脚本
│   └── .env                   #   数据库配置（DB_*/POOL_*/SHOW_*）
└── requirements.txt
```

---

## 快速开始

### 1) 安装依赖

```bash
pip install -r requirements.txt
# PyMySQL、dbutils、python-dotenv、flask、flask-restx、pydantic 等
```

### 2) 准备数据库

在你的库中执行建表（演示用 `Test/schema.sql`；正式项目按你的表结构即可）。

### 3) 配置 `.env`（放在 Flask 工程根目录）

```dotenv
# 数据库
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的密码
DB_NAME=basestudy

# 连接池（可选）
POOL_MAXCONNECTIONS=50
POOL_MINCACHED=5
POOL_MAXCACHED=20
POOL_BLOCKING=true
POOL_PING=1
POOL_AUTOCOMMIT=false

# 日志（可选）
SHOW_SQL=true
SHOW_DETAIL=false
```

### 4) Flask 中初始化

```python
from flask import Flask
from pymp.core.db_setup import init_pymp_with_pool

app = Flask(__name__)
init_pymp_with_pool(app)          # 读 .env 建连接池 + 挂 provider
# 想覆盖参数：init_pymp_with_pool(app, maxconnections=100, show_sql=True)
```

### 5) 定义模型 + Mapper

```python
from typing import Optional
from pymp.model import BaseModel, TableName, TableId, TableField

@TableName("user")
class User(BaseModel):
    id: Optional[int] = TableId()
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    createdAt: Optional[str] = None   # 列名与字段名一致；也可 TableField("created_at")
```

```python
from pymp.mapper import BaseMapper

class UserMapper(BaseMapper):
    model_class = User          # 绑定模型 -> select 自动映射 + 列白名单
    table_name = "user"         # 可省略，@TableName 会自动读取
```

### 6) 开始查询

```python
m = UserMapper()
m.insert(User(username="张三", password="123", email="z@x.com"))  # 返回自增 id
u = m.select_by_id(1)                                            # 返回 User
m.update_by_id(User(id=1, email="new@x.com"))                    # 返回受影响行数
rows = m.query().like("username", "张").order_by("id", desc=True).page_result(1, 10)
```

---

## 配置说明

所有配置集中在 `pymp.core.config` 的三个 dataclass 中，全局单例为 `global_config`。

### `DataSourceConfig`（数据源）

| 字段 | 默认 | 说明 |
|---|---|---|
| `url` | None | 例如 `mysql://user:pass@127.0.0.1:3306/db`（用于自动推断方言） |
| `host/port/user/password/database` | 127.0.0.1 / 3306 / root / "" / "" | 连接信息 |
| `charset` | utf8mb4 | 字符集 |
| `connect_timeout` | 10 | 连接超时 |

### `PoolConfig`（连接池，对标 DBUtils.PooledDB）

| 字段 | 默认 | 说明 |
|---|---|---|
| `maxconnections` | 50 | 连接池最大连接数 |
| `mincached` | 5 | 最少缓存连接 |
| `maxcached` | 20 | 最多缓存连接 |
| `maxshared` | 0 | 共享连接数（0=关） |
| `blocking` | True | 池满是否阻塞等待 |
| `maxusage` | 0 | 单连接最大复用次数（0=不限） |
| `ping` | 1 | 借出前 ping 检测 |
| `autocommit` | False | 新连接是否自动提交 |

### `Configuration`（全局）

| 字段 | 默认 | 说明 |
|---|---|---|
| `db_type / default_db_type` | None / mysql | 方言（None 自动检测） |
| `placeholder` | %s | 占位符（由方言自动维护，SQLite 为 `?`） |
| `primary_key` | id | 默认主键 |
| `map_underscore_to_camel_case` | False | 是否「DB 下划线列 ↔ Python 驼峰字段」双向映射（仅当表列名是下划线风格时开启） |
| `page_no / page_size` | 1 / 10 | 分页默认值 |
| `enable_logic_delete` | True | 逻辑删除总开关 |
| `logic_delete_column` | is_deleted | 逻辑删除列名 |
| `logic_deleted_value / logic_not_deleted_value` | 1 / 0 | 已删除 / 未删除值 |
| `show_sql` | True | 打印最终可执行 SQL |
| `show_detail` | False | 打印过程日志（事务/插件改写等） |

### `configure()` 一站式配置

```python
from pymp import configure

configure(
    connection_provider=lambda: ... ,   # 或交由 init_pymp_with_pool 自动注入
    url="mysql://...",
    db_type="mysql",                    # 也可 sqlite / postgres
    show_sql=True,
    show_detail=True,
    enable_logic_delete=True,
    map_underscore_to_camel_case=False,
    logic_delete_column="is_deleted",
)
```

---

## 环境变量 / .env 变量表

由 `pymp/core/db_setup.init_pymp_with_pool(app)` 在加载 `.env` 后读取。优先级统一为：**函数入参 > 环境变量 > 默认值**。

| 变量 | 作用 | 默认 |
|---|---|---|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | 数据库连接 | — |
| `DB_CHARSET` | 字符集 | utf8mb4 |
| `POOL_MAXCONNECTIONS` | 最大连接数 | 50 |
| `POOL_MINCACHED` | 最少缓存 | 5 |
| `POOL_MAXCACHED` | 最多缓存 | 20 |
| `POOL_MAXSHARED` | 共享连接数 | 0 |
| `POOL_BLOCKING` | 池满阻塞（true/false） | true |
| `POOL_MAXUSAGE` | 单连接复用上限 | 0 |
| `POOL_PING` | ping 检测 | 1 |
| `POOL_AUTOCOMMIT` | 自动提交 | false |
| `SHOW_SQL` | 打印 SQL 日志 | = app.debug |
| `SHOW_DETAIL` | 打印过程日志 | false |

> 布尔值支持 `1 / true / yes / on`。

---

## 日志系统

日志统一走 `pymp.core.logger`（独立 logger `"pymp"`，stdout 输出，不被 Flask 默认级别过滤）：

- `show_sql=True`：每次执行打印 **最终可执行 SQL（占位符已替换为真实值）+ 模板 + 参数**；
- `show_detail=True`：额外打印事务 `begin/commit/rollback`、插件 SQL 改写、批量等过程日志。

```python
from pymp import configure
configure(show_sql=True, show_detail=True)
# 或直接在 .env 写 SHOW_SQL=true / SHOW_DETAIL=true
```

输出示例：

```
21:16:56 INFO | 🚀 [SQL] INSERT INTO user(username) VALUES ('张三')
      模板: INSERT INTO user(username) VALUES (%s)
      参数: ['张三']
21:16:56 INFO | [tx] begin (conn=...)
21:16:56 INFO | [tx] commit
```

---

## 模型定义 BaseModel

`BaseModel` 只是“带表元信息的普通类”，不是 ORM：

```python
from typing import Optional
from pymp.model import (
    BaseModel, TableName, TableId,
    TableField, TableLogic,
)

@TableName("sys_user")
class User(BaseModel):
    id: Optional[int] = TableId()                 # 主键
    username: Optional[str] = None
    # 字段名 -> 自定义列名
    avatar: Optional[str] = TableField("avatar_url", exist=True)
    is_deleted: Optional[int] = TableLogic("is_deleted")   # 逻辑删除标记列
    created_at: Optional[str] = TableField(fill_on_insert="now")
```

- `@TableName(name)`：指定表名；不写则回退类名小写。
- `TableId()` / `TableField(...)` / `TableLogic(...)`：字段级标记（`exist=False` 表示非表字段）。
- `to_dict(exclude_none=False)` / `from_dict(data)` / `table_meta()` / `table_name()`。
- 字段默认值是 `Field` 描述符（如 `id = TableId()`）时，实例化未赋值自动落 `None`，不会把 Field 对象带进数据。

> 表名/列名与 Python 字段名约定：默认“一致即可”。需要「python 驼峰 ↔ DB 下划线」自动互转时，开启 `map_underscore_to_camel_case=True`（此时 DB 列必须为下划线风格）。

---

## Mapper 与内置 CRUD

```python
class UserMapper(BaseMapper):
    model_class = User
    # table_name = "user"
```

| 方法 | 说明 |
|---|---|
| `insert(entity)` | 实体或 dict；去 None、自动填充插件、字段→列名映射；返回自增主键 |
| `update_by_id(entity)` | 需含主键；返回受影响行数 |
| `select_by_id(pk)` | 返回模型或 None（逻辑删除插件下自动排除已删行） |
| `query()` | 返回 `Query` 链式对象（见下） |
| `delete_by_id_anno/...` | 自定义方法（见注解式 SQL） |

```python
m = UserMapper()

# 插入
uid = m.insert(User(username="张三", password="123", email="z@x.com"))

# 查询
u = m.select_by_id(uid)

# 更新（只更新非 None 字段）
affected = m.update_by_id(User(id=uid, email="new@x.com"))

# 自定义连接：子类可覆写 get_connection()，默认走全局 provider
```

> 写路径会自动把 **Python 字段名映射为真实 DB 列名**：显式 `TableField(col=...)` 优先；开启驼峰约定时转下划线；dict 输入视为已是列名不做转换。

---

## QueryWrapper 链式查询

`mapper.query()` 返回 `Query`，列名/表名自动做白名单与防注入校验。

```python
q = m.query()

# 条件
q.eq("username", "zhang")            # =
q.ne("status", 0)                    # <>
q.gt("age", 18) / ge / lt / le
q.like("name", "张")                 # LIKE %张%
q.in_("id", [1, 2, 3])               # IN（列名同样安全校验）
q.is_null("email")                   # IS NULL

# 排序 / 截断 / 分页
q.order_by("created_at", desc=True)
q.limit(10)
q.page(2, 10)

# 执行
q.list()                             # List[dict|Model]
q.one()                              # 第一条
q.count()                            # COUNT
q.page_result(1, 10)                 # -> Page（自动 count + 查询）
```

示例：

```python
rows = (
    m.query()
    .like("username", "张")
    .gt("id", 10)
    .order_by("id", desc=True)
    .page_result(1, 10)
)
```

> 分页走 `LIMIT/OFFSET` 占位符，占位符风格跟随方言（SQLite `?` / MySQL `%s`）。

---

## 注解式 SQL

在 Mapper 方法上用注解，SQL 里用 `#{name}` 取形参：

```python
from pymp.annotation import select, insert, update, delete

class UserMapper(BaseMapper):
    model_class = User

    @select("SELECT * FROM user WHERE id = #{id}")
    def select_by_id_anno(self, id: int): ...

    @select("SELECT * FROM user WHERE username LIKE #{username}", one=False)
    def search(self, username: str): ...

    @insert("INSERT INTO user(username, password) VALUES (#{username}, #{password})")
    def add(self, username: str, password: str): ...

    @update("UPDATE user SET email = #{email} WHERE id = #{id}")
    def update_email(self, id: int, email: str): ...

    @delete("DELETE FROM user WHERE id = #{id}")
    def remove(self, id: int): ...
```

要点：

- `#{name}` → 预编译占位符（防注入）；方法可额外 `return {extra: ...}` 合并参数。
- `${name}` → 受控字符串替换，仅用于排序字段/表名等，**自动安全校验**（非法标识符会抛 `SafeNameError`）。
- `@select` 单/多条由方法名启发式推断（含 `_by_` 且不以 `s` 结尾 → 单条），不确定时显式 `one=False`。
- `@update` / `@delete` 默认**禁止无 WHERE**（防全表更新/清空），确需请 `allow_empty_where=True`。
- 返回值：`@insert` 返回自增主键；`@update/@delete` 返回受影响行数。

---

## 动态 SQL

支持 MyBatis `<if>` / `<foreach>` 子集（写在三引号模板里）：

```python
@select("""
    SELECT * FROM user
    WHERE 1 = 1
    <if test="username != None"> AND username LIKE #{username}</if>
    <if test="min_id > 0"> AND id > #{min_id}</if>
    <foreach collection="ids" item="id"
             open=" AND id IN (" separator="," close=")">
        #{id}
    </foreach>
""", one=False)
def search(self, username=None, min_id=0, ids=None): ...
```

> `test` 是受控的极简表达式（`params` 键、`None/True/False`、比较、`and/or/not/in/is`）。复杂逻辑建议在 Python 里拼或用 QueryWrapper。

---

## 分页 Page

```python
from pymp.model import Page

p: Page = m.query().like("username", "张").page_result(1, 10)
p.records          # 当前页数据
p.total            # 总条数
p.page / p.size    # 页码 / 每页条数
p.pages            # 总页数（属性）
p.has_next / p.has_prev
p.to_dict()        # 直接可用于 JSON（含 current/has_next 等别名）
```

---

## 事务 transaction / @transactional

框架已修复“Executor 逐句自动提交导致事务失效”的问题。事务内所有 `Executor / get_connection()` 会**绑定同一条连接**，只有最外层事务负责提交/回滚与归还连接。

```python
from pymp import transaction, transactional

# 上下文方式
def do_transfer():
    with transaction():
        m.insert(User(username="a", ...))
        m.insert(User(username="b", ...))
        # 抛异常 -> 整体回滚；正常结束 -> 一次性提交

# 装饰器方式
@transactional
def service_method(self):
    m.insert(...)
    m.update_by_id(...)

# 显式 provider / 外部连接
with transaction(m.get_connection):
    ...
```

支持嵌套（内层只是加入外层事务，不会单独提交/回滚）。日志（`show_detail=True`）会打印 `[tx] begin/commit/rollback`。

---

## 插件机制

插件链在 `Executor` 真正执行 SQL 前统一触发 `before_execute`；实体写路径额外触发 `before_insert / before_update`。注册方式：

```python
from pymp import (
    global_interceptor_chain,
    LogicDeleteInterceptor,
    AutoFillInterceptor,
    OptimisticLockInterceptor,
    TenantInterceptor,
    TenantContext,
    BlockAttackInterceptor,
)

global_interceptor_chain.clear()
global_interceptor_chain.add_interceptor(LogicDeleteInterceptor())
global_interceptor_chain.add_interceptor(
    AutoFillInterceptor(create_time_field="created_at", update_time_field="updated_at")
)
global_interceptor_chain.add_interceptor(OptimisticLockInterceptor(version_field="version"))
global_interceptor_chain.add_interceptor(TenantInterceptor(tenant_column="tenant_id"))
global_interceptor_chain.add_interceptor(BlockAttackInterceptor())
```

| 插件 | 对标 MP | 行为 |
|---|---|---|
| `LogicDeleteInterceptor` | @TableLogic | `DELETE`→`UPDATE is_deleted=1`；`SELECT` 自动补 `is_deleted=0`（要求表真有该列） |
| `AutoFillInterceptor` | MetaObjectHandler | insert/update 自动补 `created_at / updated_at` |
| `OptimisticLockInterceptor` | @Version | 实体带 version 时自动 +1 并追加 `AND version = 旧值`；`affected=0` 即冲突 |
| `TenantInterceptor` | TenantLineInnerInterceptor | `with TenantContext(tenant_id=1):` 内自动拼 `tenant_id = ?` |
| `BlockAttackInterceptor` | BlockAttackInnerInterceptor | 无 WHERE 的 `UPDATE/DELETE` 直接抛异常拦截 |

乐观锁用法示例：

```python
cur = m.select_by_id(uid)                 # 读回 version（如 1）
affected = m.update_by_id(User(id=uid, username="新名", version=cur.version))
# affected == 0 说明期间版本已变化（乐观锁冲突），需重查重试
```

---

## 连接池与连接管理

- `Executor` 是唯一执行入口：**连接用后自动 `close()` 归还连接池**（PooledDB 必须 close 才归还），杜绝连接泄漏。
- 事务期间连接被绑定到当前线程/协程，**不中途归还**，由最外层事务统一提交/回滚后归还。
- `context.py.is_db_connection()` 用于区分“外部连接对象”与“取连接函数”（sqlite3.Connection 自身可调用，不会被误调用）。
- 支持直接传连接对象：`Executor(conn)` / `transaction(conn)`（视为外部连接，不负责关闭）。

连接池从外部配置（详见上文 `.env` 变量表）：

```python
from pymp import PoolConfig
from pymp.core.db_setup import init_pymp_with_pool

init_pymp_with_pool(app, pool=PoolConfig(maxconnections=100, mincached=10))
init_pymp_with_pool(app, maxconnections=80, blocking=True)   # 细项覆盖亦可
```

---

## 代码生成器

从 MySQL 逆向生成 Model + Mapper 代码：

```bash
python -m pymp.generator.cli \
    --host localhost --port 3306 --user root --password xxx \
    --db basestudy --table user --output ./out
```

---

## Test 演示工程

`Test/` 是一个基于 **Flask + flask_restx** 的可运行演示（Swagger 地址 `/docs`）。

运行步骤：

```bash
# 1) 建表（在 MySQL 执行 Test/schema.sql；已有表则补列）
# 2) 配置 Test/.env（DB_* / POOL_* / SHOW_*）
python Test/app.py        # http://127.0.0.1:8080/docs
```

主要测试接口（前缀 `/api/users`）：

| 方法 / 路径 | 演示点 |
|---|---|
| `GET /api/users` | 分页 + 关键字/最小 id 过滤 |
| `POST /api/users` | `BaseMapper.insert`（自动填充） |
| `GET /api/users/<id>` | `select_by_id` |
| `PUT /api/users/<id>` | `update_by_id` |
| `DELETE /api/users/<id>` | `@delete` → 逻辑删除 |
| `GET /api/users/all · /search · /order` | `@select`（多条/模糊/${order_by}） |
| `GET /api/users/count · /query-demo` | `QueryWrapper`（count/in_/gt/is_null/limit） |
| `PUT /api/users/<id>/optimistic` | 乐观锁冲突（affected=0） |
| `GET /api/users/tenant-demo?tid=` | 多租户隔离 |
| `POST /api/users/anno-demo` | `@insert` 注解 |
| `PUT /api/users/<id>/email` | `@update` 注解 |
| `PUT /api/users/no-where-demo` | 无 WHERE 的 @update 被拦截 |
| `POST /api/users/tx-rollback-demo · /tx-commit-demo` | 事务回滚 / 一次提交 |

> `Test/schema.sql` 建的是含 `is_deleted / version / tenant_id` 等列的 `user` 表。如果插件已注册但表缺列，SQL 会报 `Unknown column`——请先建表/补列，或注释掉对应插件。

---

## 已知限制与注意事项

1. **逻辑删除插件要求表真实存在逻辑删除列**（默认 `is_deleted`），否则 SELECT 会报 Unknown column。
2. `@select` 单/多条靠方法名启发式推断，不确定时显式 `one=False` 更稳。
3. SQL 改写类插件基于“括号/引号感知的顶层扫描”，不做完整 SQL AST；对复杂 CTE、带别名多表 UPDATE/DELETE 等建议业务层自行处理。
4. `dynamic <if test>` 是受控的极简表达式，复杂条件请在 Python 层拼装或用 QueryWrapper。
5. `map_underscore_to_camel_case=True` 的语义是“DB 下划线列 ↔ Python 驼峰字段”，若你的表列名本身就是驼峰请保持默认 `False`。
6. 结果映射会把 `datetime → str`、`Decimal → float`（JSON 友好），如需原始类型可后续扩展为可配置。
7. `init_pymp_with_pool` 面向 Flask + PyMySQL；其它 Web 框架/驱动可用 `configure(connection_provider=...)` 自行接入。
8. `executemany`（批量）目前不经过 SQL 改写类插件（参数布局难保证）。

---

*本文档基于当前仓库源码生成，如与实际代码有出入，以源码为准。*
