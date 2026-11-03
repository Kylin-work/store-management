# 门店会员管理系统
[![CI](https://github.com/Kylin-work/store-management/actions/workflows/ci.yml/badge.svg)](https://github.com/Kylin-work/store-management/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.16-A30000)
![MySQL](https://img.shields.io/badge/MySQL-8.4-4479A1?logo=mysql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![uv](https://img.shields.io/badge/Package_Manager-uv-DE5FE9)
![Ruff](https://img.shields.io/badge/Code_Style-Ruff-D7FF64?logo=ruff&logoColor=black)

一个基于 Django REST Framework 的多门店会员管理系统，采用前后端分离架构，支持门店管理、角色权限、会员管理、商品管理、交易收银、数据看板及操作审计。

> **项目状态：** 后端业务功能已完成，Docker 部署配置已完成，本地部署验收通过。前端尚未开始。

## 项目背景

本项目面向多门店经营场景，重点解决多门店环境下的用户身份、角色权限和业务数据隔离问题。

系统采用统一账号体系：一个用户可以关联多个门店，并在不同门店拥有不同角色。用户登录时选择门店，后续请求根据 JWT 中的门店上下文进行权限校验和数据隔离。

项目采用 Monorepo 组织代码，前后端分离开发与部署。目前已完成后端。

## 技术栈

| 分类 | 技术 |
|---|---|
| 后端框架 | Django 5.2 |
| API 框架 | Django REST Framework |
| 身份认证 | SimpleJWT |
| 数据库 | MySQL 8.4 |
| 缓存服务 | Redis 7 |
| Python 包管理 | uv |
| Web 服务 | Gunicorn |
| 容器化 | Docker、Docker Compose |
| 代码质量 | Ruff |
| 测试 | pytest |
| 前端规划 | Vue 3、TypeScript、Vite、Element Plus、Pinia |

## 核心功能

### 账号与门店管理

- 自定义用户模型，使用 8 位数字工号登录。
- 用户可关联多个门店。
- 支持不同门店配置不同角色。
- 支持门店创建、编辑、启用和停用。
- 支持账号管理及门店角色分配。

### 动态角色权限

- 角色支持动态创建和配置。
- 权限码由业务模块统一注册并同步到数据库。
- 菜单、接口和字段使用统一权限体系。
- Token 请求时重新校验门店角色及权限状态。

### 会员管理

- 会员创建、查询和编辑。
- 会员充值及充值流水。
- 会员等级调整。
- 会员积分调整。
- 门店内手机号唯一约束。

### 商品管理

- 商品创建、查询、编辑和软删除。
- 商品库存管理及库存调整。
- 根据权限控制成本价字段可见性。
- 商品数据按门店隔离。

### 交易管理

- 商品收银及交易明细。
- 多种支付方式。
- 交易完成时联动扣减库存和增加积分。
- 支持全额退款和部分退款。
- 退款时联动回滚库存及扣减对应积分。
- 店员只能查看自己经手的交易。

### 数据看板

- 今日经营概览。
- 热销商品排行。
- 会员消费排行。
- 交易趋势统计。

### 操作审计

- 记录关键业务操作。
- 保存操作人、门店、操作类型及变更详情。
- 审计日志禁止修改和删除。
- 平台管理员专属查询。

## 系统架构

```text
                    前端（规划中）
             Vue 3 + TypeScript + Vite
                         |
                         | HTTP API
                         |
                 Django REST Framework
                         |
          +--------------+--------------+
          |              |              |
       认证权限        业务模块        公共组件
          |              |              |
          |       +------+------+       |
          |       |      |      |       |
          |     会员   商品   交易      |
          |       |      |      |       |
          |       +------+------+       |
          |              |              |
          +--------------+--------------+
                         |
                 +-------+-------+
                 |               |
               MySQL           Redis
```

### 权限控制设计

系统采用四层权限控制：

1. 数据隔离：通过查询集和查询条件限制门店数据范围。
2. 接口权限：通过自定义权限类控制接口访问。
3. 对象权限：校验具体业务对象的归属关系。
4. 字段权限：根据用户权限动态控制序列化字段。

权限码采用 `模块:动作` 格式，例如：

- `member:recharge`
- `product:edit_cost`
- `transaction:refund`
- `dashboard:view`

## 项目结构

```text
store-management/
├── backend/                 # Django 后端
│   ├── apps/                # 业务模块
│   ├── config/              # Django 配置
│   ├── core/                # 公共基础设施
│   ├── Dockerfile
│   ├── manage.py
│   └── pyproject.toml
├── docker/
│   └── mysql/
│       └── init/            # MySQL 初始化脚本
├── docker-compose.yml
├── README.md
└── .gitignore
```

## 部署架构

项目使用 Docker Compose 编排后端及基础服务。

| 服务 | 技术 | 容器端口 | 本地映射端口 |
|---|---|---:|---:|
| 后端 API | Django + Gunicorn | 8000 | 18000 |
| 数据库 | MySQL 8.4 | 3306 | 13306 |
| 缓存服务 | Redis 7 | 6379 | 16379 |

后端采用多阶段 Docker 构建，并使用非 root 用户运行。

容器启动时自动执行数据库迁移和权限码同步。

本地部署配置已完成验证。正式公网部署所需的域名、反向代理及 HTTPS 配置属于后续工作。

## 项目验收

当前已完成：

- 后端业务模块测试：235 passed，3 subtests passed。
- Ruff 代码检查通过。
- Ruff 格式检查通过。
- Django 系统检查通过。
- 数据库迁移检查通过。
- Docker 镜像构建成功。
- Docker Compose 配置检查通过。
- MySQL、Redis、Django 容器正常运行。
- 数据库迁移和权限码同步成功。
- Gunicorn 3 个 Worker 正常启动。
- 生产环境 Django 部署检查完成。

## 项目进度

### 已完成

- v0.1.0：基础设施、认证、权限、账号、门店、菜单及操作日志。
- v0.2.0：会员管理、充值及会员等级。
- v0.3.0：商品管理、成本价权限及软删除。
- v0.4.0：交易收银、库存联动及积分联动。
- v0.5.0：数据看板。
- v0.6.0：Docker 部署及基础配置。
- v0.7.0：会员积分调整及商品库存调整。
- v0.8.0：部分退款及相关业务联动。
- 后续：业务测试完善、路由整理、生产配置和 Docker 部署验收。

### 尚未开始

- Vue 3 前端开发。
- 前后端联调。
- GitHub Actions CI。

## 文档

后端环境配置、启动方式、Docker 操作、API 清单及测试命令见：

[`backend/README.md`](backend/README.md)
