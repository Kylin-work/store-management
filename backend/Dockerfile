# ============================================================
# 第一阶段：构建依赖
# ============================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install --no-cache-dir uv

# 复制依赖清单并安装生产依赖
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ============================================================
# 第二阶段：生产运行环境
# ============================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安装 MySQL 运行时动态库
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd --create-home --shell /usr/sbin/nologin app

# 复制 uv
COPY --from=builder /usr/local /usr/local

# 复制 Python 虚拟环境并设置权限
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# 复制项目源码
COPY --chown=app:app . .

EXPOSE 8000

# 使用非 root 用户运行
USER app

CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]