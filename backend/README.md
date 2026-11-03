# 门店会员管理系统 - 后端开发文档

本文档用于说明 Django 后端的环境配置、运行方式、Docker 部署、API 接口及代码质量检查。

项目整体介绍和系统架构见根目录 `README.md`。

## 一、技术栈

| 分类 | 技术 |
|---|---|
| Python | 3.12+ |
| Web 框架 | Django 5.2 |
| API 框架 | Django REST Framework |
| 身份认证 | SimpleJWT |
| 数据库 | MySQL 8.4 |
| 缓存服务 | Redis 7 |
| 包管理 | uv |
| Web 服务 | Gunicorn |
| 测试 | pytest |
| 代码检查 | Ruff |

版本约束：

- Django >= 5.2, < 5.3
- djangorestframework >= 3.16, < 4
- djangorestframework-simplejwt >= 5.5, < 6
- Python >= 3.12

## 二、目录结构

```text
backend/
├── apps/
│   ├── accounts/        # 用户、角色、权限及认证
│   ├── stores/          # 门店管理
│   ├── members/         # 会员、充值及积分
│   ├── products/        # 商品及库存
│   ├── transactions/    # 交易及退款
│   ├── dashboard/       # 数据看板
│   ├── menus/           # 菜单
│   └── logs/             # 操作日志
├── config/
│   └── settings/
│       ├── base.py      # 公共配置
│       ├── dev.py       # 开发环境
│       └── prod.py      # 生产环境
├── core/                # 公共业务基础设施
├── manage.py
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

## 三、本地开发环境

### 3.1 环境要求

- Python 3.12+
- uv
- MySQL 8.4

### 3.2 安装依赖

在 backend 目录执行：

```bash
uv sync
```

### 3.3 配置环境变量

本地直接运行 Django 时，可以在 `backend/.env` 中配置：

```dotenv
DJANGO_SECRET_KEY=本地开发密钥
DB_NAME=store_management
DB_USER=dj
DB_PASSWORD=数据库密码
DB_HOST=127.0.0.1
DB_PORT=3306
```

`base.py` 会通过 `python-dotenv` 加载 `backend/.env`。

### 3.4 数据库准备

确保 MySQL 已创建数据库及对应用户。

示例 SQL：

```sql
CREATE DATABASE store_management
DEFAULT CHARSET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE USER 'dj'@'localhost'
IDENTIFIED BY '你的密码';

GRANT ALL PRIVILEGES ON store_management.*
TO 'dj'@'localhost';
```

如果使用 Docker Compose 部署，不需要另外执行上述数据库创建操作，MySQL 容器首次初始化时会根据环境变量创建数据库及用户。

### 3.5 数据库迁移

```bash
uv run python manage.py migrate
```

### 3.6 权限码同步

```bash
uv run python manage.py sync_permissions
```

### 3.7 创建超级管理员

```bash
uv run python manage.py createsuperuser
```

按照提示输入工号、手机号、姓名和密码。

## 四、Docker 部署

Docker Compose 文件位于项目根目录，而不是 backend 目录。

### 4.1 环境变量配置

在项目根目录创建 `.env`，主要配置：

```dotenv
DJANGO_SECRET_KEY=强随机密钥
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

MYSQL_ROOT_PASSWORD=MySQL管理员密码

DB_NAME=store_management
DB_USER=dj
DB_PASSWORD=应用数据库密码
```

其他生产安全配置可以根据实际需求配置，具体以 `.env.example` 和 `docker-compose.yml` 为准。

注意：

- 根目录 `.env` 由 Docker Compose 读取。
- `backend/.env` 由 Django 的 `load_dotenv()` 加载。
- 两者用途不同。
- 真实密钥和密码不得提交到 Git。

### 4.2 构建并启动

在项目根目录执行：

```bash
docker compose up -d --build
```

### 4.3 查看服务状态

```bash
docker compose ps
```

### 4.4 查看后端日志

```bash
docker compose logs backend
```

### 4.5 查看数据库日志

```bash
docker compose logs db
```

### 4.6 进入后端容器

```bash
docker compose exec backend sh
```

### 4.7 容器启动流程

后端容器启动时自动执行：

1. Django 数据库迁移。
2. 权限码同步。
3. Gunicorn 启动。

MySQL 首次初始化时会执行 `docker/mysql/init/` 中的初始化脚本。

### 4.8 本地连接地址

| 服务 | 地址 |
|---|---|
| Django API | `http://127.0.0.1:18000` |
| MySQL | `127.0.0.1:13306` |
| Redis | `127.0.0.1:16379` |

容器之间使用 Compose 服务名通信：

- MySQL：`db:3306`
- Redis：`redis:6379`

宿主机访问容器服务时使用映射端口。

### 4.9 停止服务

```bash
docker compose down
```

此操作默认不会删除持久化数据卷。

不要随意使用 `docker compose down -v`，该命令会删除 Compose 管理的数据卷。

## 五、API 接口清单

统一 API 前缀：

`/api/v1/`

### 5.1 认证

| 方法   | 路径                    | 说明       |
| ---- | --------------------- | -------- |
| POST | `/api/v1/auth/login/` | 用户登录     |
| GET  | `/api/v1/auth/me/`    | 获取当前用户信息 |

### 5.2 门店

| 方法                | 路径                                   | 说明        |
| ----------------- | ------------------------------------ | --------- |
| GET               | `/api/v1/stores/`                    | 获取门店选项列表  |
| GET / POST        | `/api/v1/stores/manage/`             | 门店管理列表、创建 |
| GET / PUT / PATCH | `/api/v1/stores/manage/<pk>/`        | 门店详情、编辑   |
| PATCH             | `/api/v1/stores/manage/<pk>/status/` | 门店启用、停用   |

### 5.3 菜单

| 方法  | 路径               | 说明         |
| --- | ---------------- | ---------- |
| GET | `/api/v1/menus/` | 获取当前用户可见菜单 |

### 5.4 账号管理

| 方法                | 路径                                              | 说明        |
| ----------------- | ----------------------------------------------- | --------- |
| GET / POST        | `/api/v1/accounts/`                             | 账号列表、创建   |
| GET / PUT / PATCH | `/api/v1/accounts/<employee_code>/`             | 账号详情、编辑   |
| PATCH             | `/api/v1/accounts/<employee_code>/status/`      | 账号启用、停用   |
| PUT               | `/api/v1/accounts/<employee_code>/store-roles/` | 替换账号的门店角色 |

### 5.5 角色与权限

| 方法                | 路径                      | 说明      |
| ----------------- | ----------------------- | ------- |
| GET / POST        | `/api/v1/roles/`        | 角色列表、创建 |
| GET / PUT / PATCH | `/api/v1/roles/<code>/` | 角色详情、编辑 |
| GET               | `/api/v1/permissions/`  | 获取权限码列表 |

### 5.6 会员

| 方法                | 路径                               | 说明      |
| ----------------- | -------------------------------- | ------- |
| GET / POST        | `/api/v1/members/`               | 会员列表、创建 |
| GET / PUT / PATCH | `/api/v1/members/<pk>/`          | 会员详情、编辑 |
| POST              | `/api/v1/members/<pk>/recharge/` | 会员充值    |
| PATCH             | `/api/v1/members/<pk>/level/`    | 调整会员等级  |
| PATCH             | `/api/v1/members/<pk>/points/`   | 调整会员积分  |

### 5.7 商品

| 方法                         | 路径                             | 说明          |
| -------------------------- | ------------------------------ | ----------- |
| GET / POST                 | `/api/v1/products/`            | 商品列表、创建     |
| GET / PUT / PATCH / DELETE | `/api/v1/products/<pk>/`       | 商品详情、编辑、软删除 |
| PATCH                      | `/api/v1/products/<pk>/stock/` | 调整商品库存      |

成本价字段根据用户权限控制可见性。

### 5.8 交易

| 方法         | 路径                                  | 说明        |
| ---------- | ----------------------------------- | --------- |
| GET / POST | `/api/v1/transactions/`             | 交易列表、创建交易 |
| GET        | `/api/v1/transactions/<pk>/`        | 交易详情      |
| POST       | `/api/v1/transactions/<pk>/refund/` | 交易退款      |

退款支持全额退款和部分退款。

### 5.9 数据看板

| 方法  | 路径                                     | 说明     |
| --- | -------------------------------------- | ------ |
| GET | `/api/v1/dashboard/summary/`           | 今日经营概览 |
| GET | `/api/v1/dashboard/top-products/`      | 热销商品排行 |
| GET | `/api/v1/dashboard/top-members/`       | 会员消费排行 |
| GET | `/api/v1/dashboard/transaction-trend/` | 交易趋势   |

### 5.10 操作日志

| 方法  | 路径                        | 说明     |
| --- | ------------------------- | ------ |
| GET | `/api/v1/operation-logs/` | 操作日志列表 |

支持按 `module`、`action`、`user_employee_code`、`start_time`、`end_time` 筛选。

## 六、统一响应格式

成功响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

错误响应：

```json
{
  "code": 10001,
  "message": "参数校验失败",
  "data": {
    "phone": ["手机号已存在"]
  }
}
```

列表响应：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

## 七、测试

在 backend 目录执行。

运行全部测试：

```bash
uv run pytest
```

运行指定模块测试：

```bash
uv run pytest apps/products/tests/ -v
```

当前业务测试验收结果：

- 235 passed
- 3 subtests passed

## 八、代码质量检查

### 8.1 Ruff 代码检查

```bash
uv run ruff check .
```

### 8.2 Ruff 格式检查

```bash
uv run ruff format --check .
```

### 8.3 Django 系统检查

```bash
uv run python manage.py check
```

### 8.4 生产环境配置检查

```bash
DJANGO_ALLOWED_HOSTS=localhost uv run python manage.py check --deploy --settings=config.settings.prod
```

### 8.5 数据库迁移检查

```bash
uv run python manage.py makemigrations --check --dry-run
```

## 九、环境配置说明

项目 Settings 分为三个层次：

| 文件 | 职责 |
|---|---|
| `config/settings/base.py` | 公共配置 |
| `config/settings/dev.py` | 开发环境配置 |
| `config/settings/prod.py` | 生产环境配置 |

Docker Compose 当前使用：

```text
config.settings.prod
```

生产配置默认启用 HTTPS 强制跳转，并提供安全 Cookie、代理 HTTPS 识别及 HSTS 相关设置。

目前尚未配置正式公网域名、反向代理及 HTTPS 证书，因此 HSTS 保持未启用状态。

