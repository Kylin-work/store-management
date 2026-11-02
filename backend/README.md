# 门店会员管理系统

多门店会员管理后端系统,支持按门店分角色的权限体系、门店/账号/角色管理、菜单权限、操作审计。

## 技术栈

- 后端：Django 5.2 LTS + Django REST Framework
- 认证：JWT(djangorestframework-simplejwt)
- 数据库：MySQL 8.4
- 缓存：Redis(预留,当前用于限流)
- 依赖管理：uv
- 前端：Vue 3 + TypeScript(开发中)
- 部署：Docker Compose(规划中)

## 权限设计

系统的核心是按门店分角色的权限模型。

### 角色与门店

一个用户在系统里只有一个账号(工号 + 密码),但在不同门店可以有不同角色。
例如张三在 A 店是店长、在 B 店是店员,登录时选择门店,本次会话的权限由该门店下的角色决定。

三张表表达这个关系：

- Store：门店
- Role：角色,可动态扩展,权限码存数据库
- UserStoreRole：用户-门店-角色三列关联,(user, store) 唯一

### 权限码

权限码格式 模块:动作,如 member:recharge、product:edit_cost。

- 权限码由各业务模块在 apps.py 里声明,sync_permissions 命令同步到 Permission 表
- 角色和权限码通过 M2M 关联,管理员可在后台分配
- 菜单可见性、接口权限、前端按钮判断共用同一套权限码

### 四道校验

| 校验层 | 位置 | 回答的问题 |
| --- | --- | --- |
| 数据隔离 | ViewSet 的 get_queryset | 能看到哪些数据(按门店过滤) |
| 接口级权限 | HasPerm 子类 | 这个角色能否调用这个接口 |
| 对象级权限 | has_object_permission | 能否操作这条具体数据 |
| 字段级可见性 | 序列化器动态移除字段 | 不同角色看到哪些字段 |

### 认证流程

1. GET /api/v1/stores/ 获取门店列表(公开,不需要登录)
2. POST /api/v1/auth/login/ 传工号、密码、门店 ID,返回 JWT
3. JWT payload 带 user_id、store_id、role_code
4. 后续请求由 StoreJWTAuthentication 校验 token 里的门店角色是否仍有效,加载权限码集合挂到 request.perm_set
5. 权限变更后,旧 token 立即失效,不需要等过期

平台管理员(is_superuser)不绑定门店,登录时门店 ID 可为空,权限全放行。

## 项目结构

store-management/
├── backend/
│   ├── config/              # Django 配置(settings 拆分为 base/dev/prod)
│   ├── core/                # 横切基础设施
│   │   ├── codes.py         # 业务码常量
│   │   ├── permissions.py   # 权限注册表 + HasPerm 基类
│   │   ├── responses.py     # 统一响应封装
│   │   ├── exceptions.py    # 业务异常 + 全局异常处理器
│   │   └── pagination.py    # 统一分页器
│   ├── apps/
│   │   ├── accounts/        # 用户、角色、权限码、账号管理
│   │   ├── stores/          # 门店管理
│   │   ├── menus/           # 菜单树
│   │   └── logs/            # 操作日志
│   ├── pyproject.toml
│   ├── uv.lock
│   └── manage.py
└── README.md

每个业务包内按职责分目录：models/、serializers/、views/、permissions/、tests/。permissions/ 与 views/ 同级,权限是一等公民。

## 快速开始

### 环境要求

- Python 3.12+
- MySQL 8.4
- uv

### 1. 安装依赖

cd backend
uv sync

### 2. 配置数据库

创建 MySQL 数据库和用户：

CREATE DATABASE store_management DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'dj'@'localhost' IDENTIFIED BY '你的密码';
GRANT ALL PRIVILEGES ON store_management.* TO 'dj'@'localhost';

在 backend/.env 里配置：

DB_NAME=store_management
DB_USER=dj
DB_PASSWORD=你的密码
DB_HOST=127.0.0.1
DB_PORT=3306

### 3. 迁移和初始化

uv run python manage.py migrate
uv run python manage.py sync_permissions

### 4. 创建超级管理员

uv run python manage.py createsuperuser

依次输入工号、手机号、姓名、密码。

### 5. 启动服务

uv run python manage.py runserver

访问 http://127.0.0.1:8000/api/v1/。

## API 概览

### 公开接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/v1/stores/ | 门店列表(登录页选门店) |
| POST | /api/v1/auth/login/ | 登录 |

### 认证接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/v1/auth/me/ | 当前用户信息、门店上下文、权限码 |
| GET | /api/v1/menus/ | 当前用户可见菜单树 |

### 门店管理(平台管理员)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | /api/v1/stores/manage/ | 列表、创建 |
| GET/PUT/PATCH | /api/v1/stores/manage/<id>/ | 详情、编辑 |
| PATCH | /api/v1/stores/manage/<id>/status/ | 启用/停用 |

### 账号管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | /api/v1/accounts/ | 列表、创建(工号自动生成) |
| GET/PATCH | /api/v1/accounts/<employee_code>/ | 详情、编辑 |
| PATCH | /api/v1/accounts/<employee_code>/status/ | 启用/停用 |
| PUT | /api/v1/accounts/<employee_code>/store-roles/ | 门店角色全量替换 |

### 角色与权限码

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | /api/v1/roles/ | 列表、创建 |
| GET/PATCH | /api/v1/roles/<code>/ | 详情、编辑(含权限分配) |
| GET | /api/v1/permissions/ | 权限码列表(按模块分组) |

### 操作日志(平台管理员)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/v1/operation-logs/ | 日志列表,支持 module/action/user_employee_code/start_time/end_time 筛选 |

## 统一响应格式

成功：

{ "code": 0, "message": "ok", "data": {...} }

错误：

{ "code": 10001, "message": "参数校验失败", "data": {"phone": ["手机号已存在"]} }

业务码定义在 core/codes.py,与 HTTP 状态码分离。

## 工号生成

- 8 位纯数字,全局自增,如 00000001
- 创建用户时在事务内锁定 Sequence 行、加一、格式化
- 序列行由 data migration 预置,手动指定工号时不消耗序列
- 所有用户由后台管理员创建,不开放注册

## 操作日志

敏感操作(门店创建/编辑/启停、账号创建/编辑/启停/门店角色替换、角色创建/编辑)通过 log_operation() 显式记录。

- 日志模型禁止 update/delete,审计日志不可篡改
- 平台管理员专属查询
- 记录业务语义的变更详情(detail JSON 字段),不是原始字段 diff

## 测试

cd backend
uv run python manage.py test -v 1

当前 114 个测试,覆盖：
- 登录(成功、失败、入参校验、JWT 上下文)
- 认证类(门店角色实时校验、token 失效场景)
- 账号管理(列表权限、创建校验、工号递增、编辑、状态、门店角色替换)
- 角色管理(列表权限、创建校验、权限替换、系统角色、权限码分组)
- 门店管理(权限、CRUD、边界、公开列表)
- 菜单(权限过滤、超级管理员全量、权限变更实时生效、排序)
- 操作日志(模型约束、记录函数、查询权限、筛选、排序)

## 版本约束

- Django >=5.2,<5.3
- djangorestframework >=3.16,<4
- djangorestframework-simplejwt >=5.5,<6
- Python >=3.12