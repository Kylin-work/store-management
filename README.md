# 门店会员管理系统

> 项目状态：后端已完成，178 个测试全过，覆盖率 98%。前端和 CI 未开始。
> 运行方式、API 清单、开发文档见 `backend/README.md`。
>
> 本文档最初是项目的设计稿，已按实际开发过程修正，记录最终的系统设计。

## 一、项目定位

从零开发一个多门店会员管理系统，作为 Web 后端求职项目。核心卖点是按门店分角色的权限设计：同一个用户在不同门店可以有不同角色，登录时选择门店，后续所有操作受该门店角色约束。

前后端分离，monorepo 开发、分离部署。当前只完成后端。

## 二、技术栈

- 后端框架：Django 5.2 LTS + Django REST Framework
- 认证：SimpleJWT（>=5.5,<6）
- 数据库：MySQL 8.4（驱动 mysqlclient）
- 缓存：Redis（预留）
- Python 包管理：uv（pyproject.toml + uv.lock）
- 前端：Vue 3 + TypeScript（未开始）
- 操作系统：Ubuntu
- 部署：Docker Compose（Django + MySQL + Redis）
- 代码质量：Ruff + coverage + pip-audit

版本约束：Django >=5.2,<5.3，DRF >=3.16,<4，Python >=3.12。

## 三、数据模型

### 3.1 用户表 User（替换 Django 默认 User）

用 AbstractUser 替换默认模型，去掉 username。

字段：

- employee_code：CharField(8)，unique，登录凭证，纯数字 8 位，创建时自动生成
- phone：CharField(11)，unique，联系方式，不参与认证
- real_name：CharField(50)，真实姓名
- is_active：BooleanField，继承，表示能否登录
- last_login：DateTimeField，继承
- date_joined：DateTimeField，继承
- is_superuser：BooleanField，继承，平台管理员标识

配置：USERNAME_FIELD = ‘employee_code’，REQUIRED_FIELDS = [‘phone’, ‘real_name’]。

所有用户由后台管理员创建，不开放注册接口。平台管理员也用此模型，有工号，但不分配门店角色，用 is_superuser 区分。

### 3.2 工号生成机制

- 规则：纯数字，8 位，全局自增，如 00000001
- 实现：独立序列表 Sequence(name, current_value)，save() 时在事务内 select_for_update() 锁定、加一、格式化
- 序列行由 data migration 预置，手动指定工号时不消耗序列
- 与用户创建在同一事务中完成，任一环节失败整体回滚
- 离职用户 is_active=False 不删除，工号不产生空洞

### 3.3 门店表 Store

- name：CharField(200)，unique，门店名称
- code：CharField(50)，unique，门店编码
- store_type：CharField(20)，choices，直营店/加盟店/旗舰店，默认直营店
- address：CharField(200)，可空，地址
- is_active：BooleanField，是否启用
- created_at / updated_at：时间戳

### 3.4 权限码表 Permission

权限码由各业务模块在 apps.py 中声明，sync_permissions 命令同步到此表。

- code：CharField(100)，unique，如 member:recharge
- name：CharField(50)，中文名
- module：CharField(100)，所属模块，用于分组展示
- is_active：BooleanField，停用后不出现在角色授权列表

### 3.5 角色表 Role

角色不写死，可后期添加。

- name：CharField(50)，unique，角色名称
- code：CharField(50)，unique，角色编码
- is_system：BooleanField，系统内置不可删
- is_active：BooleanField，停用后该角色的用户无法登录
- permissions：ManyToManyField(Permission)，角色与权限码 M2M 关联

权限码本身在代码中定义（各模块 apps.py），角色-权限映射存数据库。

### 3.6 用户门店角色表 UserStoreRole

三列关联，表达“谁、在哪个门店、是什么角色”。

- user：FK → User
- store：FK → Store
- role：FK → Role

唯一约束：(user, store)，一个用户在一个门店只有一个角色。

### 3.7 业务表

会员 Member：store FK、name、phone、balance、points、level（普通/银卡/金卡）、is_active、created_at、updated_at。同一门店内手机号唯一。

充值记录 RechargeRecord：member FK、staff FK、amount、balance_before、balance_after、created_at。充值前后余额快照用于对账。

商品 Product：store FK、name、barcode、price、cost（店员不可见）、stock、is_active、created_at、updated_at。同一门店内商品名称唯一。

交易 Transaction：store FK、member FK（可空，散客）、staff FK、total_amount、paid_amount、payment_method（现金/微信/支付宝/银行卡）、status（已完成/已退款）、created_at。

交易明细 TransactionItem：transaction FK、product FK、quantity、unit_price（成交单价快照）、subtotal。

所有业务表都带 store 外键，是数据隔离的物理基础。


## 四、权限设计

### 4.1 权限码

格式 模块:动作，如 member:recharge、product:edit_cost、transaction:refund、dashboard:view。

权限码由各模块在 apps.py 的 ready() 中调用 register_permissions 注册，sync_permissions 管理命令同步到 Permission 表。菜单可见性、接口权限、前端按钮判断共用同一套权限码。

### 4.2 登录流程

接口一：门店列表（不需要登录）

GET /api/v1/stores/ 返回所有 is_active=True 的门店 ID、名称、类型。公开信息，不需要认证。

接口二：登录

POST /api/v1/auth/login/，接收 employee_code、password、store_id。

后端校验：

1. 工号 + 密码是否正确
2. 该用户是否在 UserStoreRole 中关联了所选门店

校验通过后签发 JWT，payload 包含 user_id、store_id、role_code、is_superuser。后续请求从 token 读门店和角色，不接受客户端在请求参数中指定门店。

平台管理员（is_superuser=True）登录时不需要选择门店，token 中 store_id 为空，权限校验跳过门店隔离。

### 4.3 四道校验

- 数据隔离：ViewSet 的 get_queryset / 查询条件，非管理员强制 filter(store_id=token.store_id)，回答能看到哪些数据
- 接口级权限：自定义 HasPerm 子类，根据 request.perm_set 判断能否调用接口
- 对象级权限：视图内的归属校验（如店员只能看自己经手的交易），回答能否操作这条具体数据
- 字段级可见性：序列化器 __init__ 动态移除字段（如 cost 对店员隐藏），回答不同角色看到哪些字段

关键原则：列表接口不触发对象级权限，数据隔离必须靠 get_queryset 兜底。

认证类 StoreJWTAuthentication 每次请求都会校验 token 里的门店/角色是否仍有效，并从数据库加载权限码集合挂到 request.perm_set。权限变更后旧 token 立即失效。

## 五、统一响应规范

成功：{ “code”: 0, “message”: “ok”, “data”: ... }

错误：{ “code”: 10001, “message”: “参数校验失败”, “data”: {“phone”: [“手机号已存在”]} }

列表 data 为 { “items”: [...], “total”: n, “page”: 1, “page_size”: 20 }。

实现：

- core/responses.py 提供 success() / error() 辅助函数
- 自定义 exception_handler 挂在 DRF 的 EXCEPTION_HANDLER 配置，统一转换 ValidationError、PermissionDenied、NotFound、NotAuthenticated 和自定义 BizException
- 业务码常量集中在 core/codes.py
- HTTP 状态码仍正确设置（200/201/400/403/404），业务码独立于 HTTP 状态码
- 自定义分页器 StandardPagination 直接输出 items/total/page/page_size


## 六、菜单模块

菜单定义存数据库（data migration 初始化），每个节点含 permission_code。登录后根据当前门店的 role_code 对应权限集合，过滤返回可见菜单树。不做菜单管理界面。

初始菜单结构（一级菜单）：

- 会员管理：member:list，店长、店员可见
- 商品管理：product:list，店长可见
- 交易管理：transaction:list，店长、店员可见
- 数据看板：dashboard:view，仅店长可见
- 账号管理：account:list，平台管理员（通过 is_superuser 全放行）
- 角色管理：role:list，平台管理员（通过 is_superuser 全放行）

菜单接口 GET /api/v1/menus/ 按当前用户权限码过滤，超级管理员返回全部。

## 七、后端目录结构

backend/
├── config/              # Django 配置（settings 拆分为 base/dev/prod）
├── core/                # 横切基础设施
│   ├── codes.py         # 业务码常量
│   ├── permissions.py   # 权限注册表 + HasPerm 基类
│   ├── responses.py     # 统一响应封装
│   ├── exceptions.py    # 业务异常 + 全局异常处理器
│   └── pagination.py    # 统一分页器
├── apps/
│   ├── accounts/        # 用户、角色、权限码、账号管理、认证
│   ├── stores/          # 门店管理
│   ├── members/         # 会员、充值
│   ├── products/        # 商品
│   ├── transactions/    # 交易、退款
│   ├── dashboard/       # 数据看板（只读聚合，无 models）
│   ├── menus/           # 菜单树
│   └── logs/            # 操作日志
├── manage.py
├── pyproject.toml
└── uv.lock

结构约定：

- 每个 apps 下的模块内部按 models/、serializers/、views/、tests/ 组织
- 有跨模型业务逻辑的模块带 services/（如 members/services/recharge.py、transactions/services/create_transaction.py）
- 有独立权限类的模块带 permissions/（如 stores/permissions/store.py）
- 纯 API 项目，没有 admin.py、asgi.py
- 没有模型的模块（dashboard）不建 models/ 和 migrations/

## 八、前端约定（未开始）

- Vue 3 + TypeScript + Vite + Element Plus + Pinia
- 接口契约以 DRF 序列化器为准
- 为 UserProfile（含 role、storeId）、菜单项（含 permissionCode）定义 TS 接口类型
- 认证流程：SimpleJWT 签发 access + refresh；axios 拦截器附加 Authorization: Bearer；Vue Router 守卫校验 token 和角色；后端 DRF 权限类做最终兜底
- 登录页流程：选门店（公开接口）→ 输工号和密码 → 登录

## 九、开发进度

已完成：

- v0.1.0 基础设施：认证、权限、账号、门店、菜单、操作日志
- v0.2.0 会员模块：会员 CRUD、充值事务、等级调整、门店数据隔离
- v0.3.0 商品模块：商品 CRUD、字段级成本价可见性、软删除、权限双保护
- v0.4.0 交易模块：收银、退款、库存联动、积分联动、店员对象级隔离
- v0.5.0 数据看板：概览、热销商品、会员排行、交易趋势
- v0.6.0 部署收尾：Docker Compose、时区表自动导入、README 更新、目录清理

未完成：

- 前端（Vue 3 + TS）
- CI（GitHub Actions）
- 会员积分调整接口、商品库存调整接口、部分退款

## 十、操作日志

记录敏感操作：门店创建/编辑/启停、账号创建/编辑/启停/门店角色替换、角色创建/编辑、会员创建/编辑/充值/等级调整、商品创建/编辑/删除、交易创建/退款。

日志通过 log_operation() 显式记录，字段包括操作人、门店、模块、动作、对象类型、对象标识、变更详情、操作时间。

模型层禁止 update/delete，审计日志不可篡改。平台管理员专属查询接口。

## 十一、仓库与部署

- monorepo 开发：backend/ 和 frontend/ 同仓库
- 分离部署：前端构建产物由 Nginx 托管，后端 Django 跑 API 服务
- 根目录 docker-compose.yml 编排 Django + MySQL + Redis，MySQL 容器首次启动自动导入时区表
- 根目录 .gitignore 排除 frontend/node_modules/、frontend/dist/、backend/__pycache__/、backend/staticfiles/、.env、.coverage、htmlcov/
- backend/README.md 写清启动方式、权限设计说明、API 清单
- 根目录本文件记录系统设计和当前进度

测试：178 个，覆盖率 98%。运行 uv run python manage.py test。

代码质量：uv run ruff check . 和 uv run pip-audit。
