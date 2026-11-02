# 门店会员管理系统 · 完整设计文档

> 版本：定稿版
> 状态：所有设计决策已确认,可进入开发

---

## 一、项目定位

从零开发一个**多门店会员管理系统**,作为 Web 后端求职项目.核心卖点是**按门店分角色的权限设计**：同一个用户在不同门店可以有不同角色,登录时选择门店,后续所有操作受该门店角色约束.

前后端分离,monorepo 开发、分离部署.

## 二、技术栈

| 层 | 选型 |
|---|---|
| 后端框架 | Django 5.2 LTS + Django REST Framework |
| 认证 | SimpleJWT(`>=5.5,<6`) |
| 数据库 | MySQL 8.4(驱动 `mysqlclient`) |
| 缓存 | Redis |
| Python 包管理 | uv(`pyproject.toml` + `uv.lock`) |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia |
| 操作系统 | Ubuntu |
| 部署 | Docker Compose(Django + MySQL + Redis);开发阶段用本地 MySQL 和 Redis |

**版本约束**：Django `>=5.2,<5.3`,DRF `>=3.16,<4`,Python `>=3.12`.

## 三、数据模型

### 3.1 用户表(User,替换 Django 默认 User)

用 `AbstractUser` 替换默认模型,去掉 `username`.

| 字段 | 类型 | 说明 |
|---|---|---|
| employee_code | CharField(8), unique | 登录凭证,纯数字 8 位,创建时自动生成 |
| phone | CharField, unique | 联系方式,不参与认证 |
| real_name | CharField | 真实姓名 |
| is_active | BooleanField | 继承,表示能否登录 |
| last_login | DateTimeField | 继承 |
| date_joined | DateTimeField | 继承 |
| is_superuser | BooleanField | 继承,平台管理员标识 |

- `USERNAME_FIELD = 'employee_code'`,`REQUIRED_FIELDS = []`
- `first_name` / `last_name` 保留但不暴露给前端
- **所有用户由后台管理员创建,不开放注册接口**
- 平台管理员也用此模型,有工号,但不分配门店角色,用 `is_superuser` 区分

### 3.2 工号生成机制

- 规则：纯数字,8 位,全局自增,如 `00000001`
- 实现：独立序列表 `Sequence(name, current_value)`,`save()` 时在事务内 `select_for_update()` 锁定、加一、格式化
- 与用户创建在同一事务中完成,任一环节失败整体回滚,给管理员返回明确错误让其重试
- 不静默重试;离职用户 `is_active=False` 不删除,工号不产生空洞

### 3.3 门店表(Store)

| 字段 | 类型 | 说明 |
|---|---|---|
| name | CharField | 门店名称 |
| code | CharField, unique | 门店编码 |
| address | CharField | 地址 |
| is_active | BooleanField | 是否启用 |

### 3.4 角色表(Role)

角色不写死,可后期添加.

| 字段 | 类型 | 说明 |
|---|---|---|
| name | CharField | 角色名称(店长、店员…) |
| code | CharField, unique | 角色编码(store_manager、staff…) |
| is_system | BooleanField | 系统内置不可删 |
| permissions | JSONField | 权限码列表,如 `["member:list", "member:recharge"]` |

- **权限码常量**集中在 `core/permissions.py` 定义,作为唯一来源
- **角色-权限映射**存数据库(`Role.permissions` JSON 字段)
- 保存角色时在应用层校验：列表中每个权限码必须在 `core/permissions.py` 允许集合内,否则拒绝保存
- 后续如需按权限点反查角色,可迁移到 `RolePermission` 关联表

### 3.5 用户门店角色表(UserStoreRole)

三列关联,表达“谁、在哪个门店、是什么角色”.

| 字段 | 类型 | 说明 |
|---|---|---|
| user | FK → User | |
| store | FK → Store | |
| role | FK → Role | |

**唯一约束**：`(user, store)` —— 一个用户在一个门店只有一个角色.多角色可作为后续扩展点(放宽到 `(user, store, role)` 并做权限并集).

### 3.6 业务表

- **Member**：`store` FK、`name`、`phone`、`balance`、`points`、`level`
- **Product**：`store` FK、`name`、`price`、`cost`(店员不可见)、`stock`
- **Transaction**：`store` FK、`member` FK、`staff` FK、`product` FK、`quantity`、`total_amount`、`created_at`

所有业务表都带 `store` 外键,是数据隔离的物理基础.

## 四、权限设计

### 4.1 权限码

格式 `模块:动作`,如 `member:list`、`member:recharge`、`product:edit_cost`、`transaction:refund`、`dashboard:view`.

集中在 `core/permissions.py` 定义,代码引用常量,不写字符串魔法值.菜单可见性、接口权限、前端按钮判断共用同一套权限码.

### 4.2 登录流程

**接口一：门店列表(不需要登录)**

`GET /api/stores/` 返回所有 `is_active=True` 的门店 ID 和名称.公开信息,不需要认证.

**接口二：登录**

`POST /api/auth/login/`,接收 `employee_code`、`password`、`store_id`.

后端校验：
1. 工号 + 密码是否正确.
2. 该用户是否在 `UserStoreRole` 中关联了所选门店.

校验通过后签发 JWT,payload 包含 `user_id`、`store_id`、`role_code`.后续请求从 token 读门店和角色,**不接受客户端在请求参数中指定门店**.

平台管理员(`is_superuser=True`)登录时不需要选择门店,token 中 `store_id` 为空,权限校验跳过门店隔离.

### 4.3 四道校验

| 校验层 | 位置 | 规则 |
|---|---|---|
| 数据隔离 | ViewSet 的 `get_queryset` | 非管理员强制 `filter(store_id=token.store_id)` |
| 接口级权限 | 自定义 `BasePermission.has_permission` | 根据 `role_code` 对应角色的 `permissions` 判断能否调用接口 |
| 对象级权限 | `has_object_permission` | 店员只能操作自己经手的交易;店长只能操作本店数据 |
| 字段级可见性 | 序列化器 `__init__` 动态移除字段 | `cost` 对店员隐藏 |

**关键原则**：列表接口不触发对象级权限,数据隔离必须靠 `get_queryset` 兜底.

## 五、统一响应规范

**成功**：`{ "code": 0, "message": "ok", "data": ... }`

**错误**：`{ "code": 10001, "message": "无权操作", "data": null }`

列表 `data` 为 `{ "items": [...], "total": n, "page": 1, "page_size": 20 }`.

**实现**：
- `core/responses.py` 提供 `success()` / `error()` 辅助函数
- 自定义 `exception_handler` 挂在 DRF 的 `EXCEPTION_HANDLER` 配置,统一转换 `ValidationError`、`PermissionDenied`、`NotFound` 和自定义业务异常
- 业务码常量集中在 `core/codes.py`,前端 TS 维护对应枚举
- HTTP 状态码仍正确设置(200/201/400/403/404),业务码独立于 HTTP 状态码
- 自定义分页器直接输出 `items/total/page/page_size`,不在渲染层二次转换

## 六、菜单模块

- 菜单定义**存数据库**(data migration / fixture 初始化),每个节点含 `permission_code`
- 登录后根据当前门店的 `role_code` 对应权限集合,过滤返回可见菜单树
- 不做菜单管理界面
- **初始菜单结构**(一级菜单起步)：

| 菜单 | 权限码 | 可见角色 |
|---|---|---|
| 会员管理 | `member:list` | 店长、店员 |
| 商品管理 | `product:list` | 店长 |
| 交易管理 | `transaction:list` | 店长、店员 |
| 数据看板 | `dashboard:view` | 店长 |

- 二级节点(如会员管理下的“会员列表”“会员充值”)待业务模块跑通后按需添加

## 七、后端目录结构

按业务域分包,包内按职责分目录.`core/` 为横切基础设施包.

```
backend/
├── config/                  # Django 项目配置
├── core/                    # 横切基础设施
│   ├── codes.py             # 业务码常量
│   ├── permissions.py       # 权限码常量 + 自定义权限基类
│   ├── responses.py         # success / error 辅助函数
│   ├── exceptions.py        # 自定义业务异常 + 全局 exception_handler
│   ├── pagination.py        # 自定义分页器
│   └── renderers.py         # 可选
├── apps/
│   ├── accounts/            # User, Role, UserStoreRole, Sequence
│   │   ├── apps.py
│   │   ├── __init__.py
│   │   ├── models/          # 按实体命名,__init__.py 显式导出
│   │   ├── serializers/
│   │   ├── views/
│   │   ├── permissions/     # 接口级 + 对象级,与 views 同级
│   │   ├── services/        # 跨模型业务逻辑,按需创建
│   │   ├── tests/           # test_models / test_views / test_permissions
│   │   └── urls.py
│   ├── stores/              # Store
│   ├── members/             # 会员
│   ├── products/            # 商品
│   ├── transactions/        # 交易
│   ├── dashboard/           # 看板
│   └── menus/               # 菜单
└── manage.py
```

**结构约定**：
- 每个 `__init__.py` 做显式导出,外部从包级别导入
- `models/`、`serializers/`、`views/`、`permissions/` 下按同名实体对齐文件
- `permissions/` 区分接口级权限类与对象级权限类
- `tests/` 按维度命名,权限边界测试集中在 `test_permissions.py`
- `services/` 不提前建空目录,出现跨模型业务逻辑时再建

## 八、前端约定

- Vue 3 + TypeScript + Vite + Element Plus + Pinia
- 接口契约以 DRF 序列化器为准,开启 schema 生成(`/api/schema/`),前端对照写 TS 类型
- 为 `UserProfile`(含 `role`、`storeId`)、菜单项(含 `permissionCode`)定义 TS 接口类型
- 认证流程：SimpleJWT 签发 access + refresh;axios 拦截器附加 `Authorization: Bearer`;Vue Router 守卫校验 token 和角色;后端 DRF 权限类做最终兜底,前端不承担安全职责
- 前端 `baseURL` 从环境变量读取;开发期配置 CORS
- 登录页流程：选门店(公开接口)→ 输工号和密码 → 登录

## 九、模块划分与推进顺序

**基础层**：门店 → 用户/角色/用户门店角色(含工号生成)→ 认证登录 → 菜单

**业务层**：会员 → 商品 → 交易 → 数据看板(按依赖顺序)

**支撑层**：操作日志(模型层禁止 update/delete)→ 测试(门店隔离、字段隐藏、角色越权)→ 部署文档

**第一条验证链路**：`members` 模块跑通“店长能看本店会员、店员只能看自己经手的会员”.

## 十、操作日志

记录敏感操作(会员充值、商品改价、退款),字段包括操作人、门店、对象、动作、时间.

**模型层禁止 update/delete**,审计日志不可篡改.

## 十一、仓库与部署

- **monorepo 开发**：`backend/` 和 `frontend/` 同仓库,开发期接口契约同步演进
- **分离部署**：前端构建产物由 Nginx 托管,后端 Django 跑 API 服务
- 根目录 `docker-compose.yml` 编排 Django + MySQL + Redis,确保一条命令可启动
- 根目录 `.gitignore` 排除 `frontend/node_modules/`、`frontend/dist/`、`backend/__pycache__/`、`backend/staticfiles/`、`.env`
- README 写清启动方式、权限设计说明、权限码命名规范

---

以上为定稿文档,所有设计决策均已确认.下一步进入开发,建议从 `stores` 模块的 `Store` 模型开始,再到 `accounts` 模块的 `Sequence`、`User`、`Role`、`UserStoreRole` 模型,然后是认证登录接口.
