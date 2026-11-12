"""
InsightFlow Django settings.

Reads from .env (or environment) using python-dotenv.
Required variables: SECRET_KEY, DATABASE_URL
Optional: DEBUG, ALLOWED_HOSTS, EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER,
          EMAIL_HOST_PASSWORD, EMAIL_USE_TLS, DEFAULT_FROM_EMAIL
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-change-me-in-production")
DEBUG = os.environ.get("DEBUG", "true").lower() in {"1", "true", "yes"}

ALLOWED_HOSTS_ENV = os.environ.get("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = (
    [h.strip() for h in ALLOWED_HOSTS_ENV.split(",") if h.strip()]
    if ALLOWED_HOSTS_ENV
    else ["localhost", "127.0.0.1"]
)

# ---------------------------------------------------------------------------
# Custom user model — MUST be declared before first migration
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "projects",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.NoCacheMiddleware",
]

ROOT_URLCONF = "insightflow.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "projects.context_processors.user_projects_processor",
            ],
        },
    },
]

WSGI_APPLICATION = "insightflow.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    import re

    _m = re.match(
        r"postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?]+)(\?.*)?",
        DATABASE_URL,
    )
    if _m:
        _user, _password, _host, _port, _dbname, _opts = _m.groups()
        _options = {}
        if _opts and "sslmode=require" in _opts:
            _options["sslmode"] = "require"
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": _dbname,
                "USER": _user,
                "PASSWORD": _password,
                "HOST": _host,
                "PORT": _port or "5432",
                "OPTIONS": _options,
                "CONN_MAX_AGE": 60,
            }
        }
    else:
        # Let dj-database-url style pass-through; keep it simple
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": DATABASE_URL,
            }
        }
else:
    # Fallback to SQLite for initial setup convenience (not for production)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Session & cookies
# ---------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_SECURE = not DEBUG  # True in production, False in dev (HTTP)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = not DEBUG

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Default primary key
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
_default_from = (
    os.environ.get("DEFAULT_FROM_EMAIL", "").strip()
    or os.environ.get("SMTP_FROM", "").strip()
    or "InsightFlow <noreply@insightflow.app>"
)
DEFAULT_FROM_EMAIL = _default_from

_email_backend = os.environ.get("EMAIL_BACKEND", "").strip()
_smtp_host = os.environ.get("EMAIL_HOST", "").strip() or os.environ.get("SMTP_HOST", "").strip()
_smtp_password = os.environ.get("EMAIL_HOST_PASSWORD", "").strip() or os.environ.get("SMTP_PASSWORD", "").strip()

# In dev, default to console email backend
if _email_backend:
    EMAIL_BACKEND = _email_backend
elif _smtp_host and _smtp_password and not DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = _smtp_host
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT") or os.environ.get("SMTP_PORT", 587))
    EMAIL_HOST_USER = (
        os.environ.get("EMAIL_HOST_USER") or os.environ.get("SMTP_USER", "")
    )
    EMAIL_HOST_PASSWORD = _smtp_password
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() in {"1", "true", "yes"}
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Auth redirects
# ---------------------------------------------------------------------------
LOGIN_URL = "/login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login"
