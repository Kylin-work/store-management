"""
生产环境配置。
"""

import os
from urllib.parse import urlparse

from .base import *

DEBUG = False


def get_required_env(name: str) -> str:
    """读取必填环境变量。"""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"生产环境缺少必填配置：{name}")
    return value


def get_env_list(name: str) -> list[str]:
    """读取逗号分隔的环境变量。"""
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def get_env_bool(name: str, default: bool) -> bool:
    """读取布尔环境变量。"""
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False

    raise RuntimeError(f"{name} 必须是有效的布尔值")


# ---------------------------------------------------------------------------
# 安全配置
# ---------------------------------------------------------------------------

SECRET_KEY = get_required_env("DJANGO_SECRET_KEY")

if (
    SECRET_KEY
    in {
        "change-me",
        "dev-only-insecure-key-change-me",
    }
    or len(SECRET_KEY) < 50
):
    raise RuntimeError("DJANGO_SECRET_KEY 必须使用至少 50 位的随机密钥")

ALLOWED_HOSTS = get_env_list("DJANGO_ALLOWED_HOSTS")

if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS 必须配置明确的域名，不能使用 *")

# 生产环境默认启用 HTTPS。
SECURE_SSL_REDIRECT = get_env_bool(
    "DJANGO_SECURE_SSL_REDIRECT",
    True,
)

# 要求反向代理覆盖 X-Forwarded-Proto，
# 并且后端端口不能直接暴露给不可信网络。
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"

# HTTPS 稳定运行并确认域名配置后，再设置 HSTS。
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_env_bool(
    "DJANGO_HSTS_INCLUDE_SUBDOMAINS",
    False,
)
SECURE_HSTS_PRELOAD = get_env_bool(
    "DJANGO_HSTS_PRELOAD",
    False,
)

if SECURE_HSTS_SECONDS < 0:
    raise RuntimeError("DJANGO_HSTS_SECONDS 不能小于 0")


# ---------------------------------------------------------------------------
# 数据库
# ---------------------------------------------------------------------------

DB_NAME = get_required_env("DB_NAME")
DB_USER = get_required_env("DB_USER")
DB_PASSWORD = get_required_env("DB_PASSWORD")
DB_HOST = get_required_env("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306").strip()

try:
    DB_PORT = int(DB_PORT)
except ValueError as exc:
    raise RuntimeError("DB_PORT 必须是整数") from exc

if not 1 <= DB_PORT <= 65535:
    raise RuntimeError("DB_PORT 超出有效范围")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "OPTIONS": {
            "charset": "utf8mb4",
        },
        "CONN_MAX_AGE": 60,
    }
}


# ---------------------------------------------------------------------------
# 跨域配置
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = get_env_list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = get_env_list("CSRF_TRUSTED_ORIGINS")

for origin in CORS_ALLOWED_ORIGINS + CSRF_TRUSTED_ORIGINS:
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"无效的跨域来源配置：{origin}")


# ---------------------------------------------------------------------------
# 管理后台和安全检查
# ---------------------------------------------------------------------------
