# 门店会员管理系统 - 后端

多门店会员管理后端系统，支持按门店分角色的权限体系、会员、商品、交易、看板、操作审计。

## 技术栈

- 后端：Django 5.2 LTS + Django REST Framework
- 认证：JWT（djangorestframework-simplejwt）
- 数据库：MySQL 8.4
- 缓存：Redis（预留）
- 依赖管理：uv
- 代码质量：Ruff + coverage + pip-audit

## 权限设计

系统的核心是按门店分角色的权限模型。

### 角色与门店

一个用户在系统里只有一个账号（工号 + 密码），但在不同门店可以有不同角色。登录时选择门店，本次会话的权限由该门店下的角色决定。

- Store：门店
- Role：角色，可动态扩展，权限码存数据库
- UserStoreRole：用户-门店-角色三列关联，(user, store) 唯一

### 权限码

格式 模块:动作，如 member:recharge、product:edit_cost。

- 权限码由各业务模块在 apps.py 里声明，sync_permissions 命令同步到 Permission 表
- 角色和权限码通过 M2M 关联
- 菜单可见性、接口权限、前端按钮判断共用同一套权限码

### 四道校验

- 数据隔离：ViewSet 的 get_queryset / 查询条件，回答能看到哪些数据（按门店过滤）
- 接口级权限：HasPerm 子类，回答这个角色能否调用这个接口
- 对象级权限：视图内的归属校验，回答能否操作这条具体数据
- 字段级可见性：序列化器 __init__ 动态移除字段，回答不同角色看到哪些字段

### 认证流程

1. GET /api/v1/stores/ 获取门店列表（公开）
2. POST /api/v1/auth/login/ 传工号、密码、门店 ID，返回 JWT
3. JWT payload 带 user_id、store_id、role_code
4. 后续请求由 StoreJWTAuthentication 校验 token 里的门店角色是否仍有效，加载权限码集合挂到 request.perm_set
5. 权限变更后，旧 token 立即失效

平台管理员（is_superuser）不绑定门店，权限全放行，但访问业务接口（会员、商品、交易）会因无门店上下文返回 403。

## 项目结构

```
backend/
├── config/
├── core/
├── apps/
│   ├── accounts/
│   ├── stores/
│   ├── members/
│   ├── products/
│   ├── transactions/
│   ├── dashboard/
│   ├── menus/
│   └── logs/
├── manage.py
├── pyproject.toml
└── uv.lock
```

## 快速开始

### 环境要求

- Python 3.12+
- MySQL 8.4
- uv

### 1. 安装依赖

```bash
cd backend
uv sync
```

### 2. 配置数据库

创建 MySQL 数据库和用户：

```sql
CREATE DATABASE store_management DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'dj'@'localhost' IDENTIFIED BY '你的密码';
GRANT ALL PRIVILEGES ON store_management.* TO 'dj'@'localhost';
```

导入 MySQL 时区表（看板趋势接口依赖，不导入会报 Are time zone definitions for your database installed?）：

```bash
sudo mysql_tzinfo_to_sql /usr/share/zoneinfo | sudo mysql -u root -p mysql
```

在 backend/.env 里配置：

```bash
DB_NAME=store_management
DB_USER=dj
DB_PASSWORD=你的密码
DB_HOST=127.0.0.1
DB_PORT=3306
```
如果使用 Docker Compose 部署，宿主机映射端口为 13306（MySQL）、16379（Redis）、18000（后端）。容器内部通信仍走默认端口，DB_HOST=db、DB_PORT=3306 无需修改。宿主机用客户端连容器 MySQL 时写 127.0.0.1:13306。

### 3. 迁移和初始化

```bash
uv run python manage.py migrate
uv run python manage.py sync_permissions
```

### 4. 创建超级管理员

```bash
uv run python manage.py createsuperuser
```

依次输入工号、手机号、姓名、密码。
创建后需要修复工号序列，避免后续创建普通用户时工号冲突：
```bash
uv run python manage.py fix_sequence
```

### 5. 启动服务

```bash
uv run python manage.py runserver
```

## API 概览

### 公开接口

- GET /api/v1/stores/ 门店列表（登录页选门店）
- POST /api/v1/auth/login/ 登录

### 认证接口

- GET /api/v1/auth/me/ 当前用户信息、门店上下文、权限码
- GET /api/v1/menus/ 当前用户可见菜单树

### 门店管理（平台管理员）

- GET/POST /api/v1/stores/manage/ 列表、创建
- GET/PUT/PATCH /api/v1/stores/manage/<id>/ 详情、编辑
- PATCH /api/v1/stores/manage/<id>/status/ 启用/停用

### 账号管理

- GET/POST /api/v1/accounts/ 列表、创建（工号自动生成）
- GET/PATCH /api/v1/accounts/<employee_code>/ 详情、编辑
- PATCH /api/v1/accounts/<employee_code>/status/ 启用/停用
- PUT /api/v1/accounts/<employee_code>/store-roles/ 门店角色全量替换

### 角色与权限码

- GET/POST /api/v1/roles/ 列表、创建
- GET/PATCH /api/v1/roles/<code>/ 详情、编辑（含权限分配）
- GET /api/v1/permissions/ 权限码列表（按模块分组）

### 会员

- GET/POST /api/v1/members/ 列表、创建
- GET/PATCH /api/v1/members/<pk>/ 详情、编辑
- POST /api/v1/members/<pk>/recharge/ 充值（事务内改余额、写记录、写日志）
- PATCH /api/v1/members/<pk>/level/ 等级调整（仅店长）
- PATCH /api/v1/members/<pk>/points/ 积分调整（仅店长）

### 商品

- GET/POST /api/v1/products/ 列表、创建
- GET/PATCH/DELETE /api/v1/products/<pk>/ 详情、编辑、软删除

- PATCH /api/v1/products/<pk>/stock/ 库存调整（仅店长）

cost 字段对无 product:edit_cost 权限的用户隐藏。

### 交易

- GET/POST /api/v1/transactions/ 列表、收银（扣库存、算积分）
- GET /api/v1/transactions/<pk>/ 详情（店员只能看自己经手的）
- POST /api/v1/transactions/<pk>/refund/ 退款（仅店长，支持全额和部分退款，回滚库存、按比例扣积分）

### 数据看板（仅店长）

- GET /api/v1/dashboard/summary/ 今日概览
- GET /api/v1/dashboard/top-products/ 热销商品排行
- GET /api/v1/dashboard/top-members/ 会员消费排行
- GET /api/v1/dashboard/transaction-trend/ 交易趋势（?days=7，支持 1-30）

### 操作日志（平台管理员）

- GET /api/v1/operation-logs/ 日志列表，支持 module/action/user_employee_code/start_time/end_time 筛选

## 统一响应格式

成功：{"code": 0, "message": "ok", "data": {...}}

错误：{"code": 10001, "message": "参数校验失败", "data": {"phone": ["手机号已存在"]}}

## 工号生成

- 8 位纯数字，全局自增，如 00000001
- 创建用户时在事务内锁定 Sequence 行、加一、格式化
- 序列行由 data migration 预置，手动指定工号时不消耗序列
- 所有用户由后台管理员创建，不开放注册

## 操作日志

敏感操作通过 log_operation() 显式记录。

- 日志模型禁止 update/delete，审计日志不可篡改
- 平台管理员专属查询
- 记录业务语义的变更详情（detail JSON 字段）

## 测试

```bash
cd backend
uv run python manage.py test -v 1
```

当前 178 个测试，覆盖率 98%。

```bash
uv run coverage run manage.py test
uv run coverage report -m
```

## 代码质量

```bash
uv run ruff check .
uv run pip-audit
```

## 版本约束

- Django >=5.2,<5.3
- djangorestframework >=3.16,<4
- djangorestframework-simplejwt >=5.5,<6
- Python >=3.12
