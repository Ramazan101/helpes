"""
Конфигурация Django-проекта Help Desk (внутренняя система технических заявок).
Все чувствительные параметры и подключения считываются из переменных окружения.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Загрузка переменных из файла .env, если он присутствует
load_dotenv(BASE_DIR / ".env", override=True)

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-fallback-key-do-not-use-in-prod",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "False").strip().lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# Определение установленных приложений
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Внутренние модули Help Desk
    "apps.accounts.apps.AccountsConfig",
    "apps.locations.apps.LocationsConfig",
    "apps.tickets.apps.TicketsConfig",
    "apps.assistant.apps.AssistantConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Конфигурация базы данных: PostgreSQL для сервера компании или SQLite для локального запуска
DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").strip().lower()

if DB_ENGINE in ("postgresql", "postgres", "pgsql"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "helpes_db"),
            "USER": os.environ.get("DB_USER", "helpes_user"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / os.environ.get("SQLITE_PATH", "db.sqlite3"),
        }
    }

# Кастомная модель пользователя (Техники и Администраторы)
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "tickets:tech_queue"
LOGOUT_REDIRECT_URL = "accounts:login"

# Валидация паролей
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Локализация и часовой пояс (Кыргызстан)
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Asia/Bishkek"
USE_I18N = True
USE_TZ = True

# Статические файлы
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Локальный кэш в памяти для защиты открытой формы от спама
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "helpes-rate-limit-cache",
    }
}

# Настройки безопасности куки и сессий
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    # Nginx forwards the original protocol; enable secure cookies after HTTPS is configured.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SECURE_COOKIES = os.environ.get("DJANGO_SECURE_COOKIES", "False").strip().lower() in ("true", "1", "yes")
    SESSION_COOKIE_SECURE = SECURE_COOKIES
    CSRF_COOKIE_SECURE = SECURE_COOKIES

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Параметры бизнес-логики Help Desk
STALE_TICKET_HOURS = int(os.environ.get("STALE_TICKET_HOURS", "24"))
PUBLIC_FORM_RATE_LIMIT = int(os.environ.get("PUBLIC_FORM_RATE_LIMIT", "5"))

# Параметры AI-помощника (Helpes Self-Service Assistant)
AI_API_KEY = (
    os.environ.get("AI_API_KEY", "").strip()
    or os.environ.get("OPENAI_API_KEY", "").strip()
)
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://openrouter.ai/api/v1").strip() or "https://openrouter.ai/api/v1"
AI_MODEL = os.environ.get("AI_MODEL", "openrouter/free").strip() or "openrouter/free"
AI_ASSISTANT_TIMEOUT = float(os.environ.get("AI_ASSISTANT_TIMEOUT", "15"))
AI_ASSISTANT_MAX_TOKENS = int(os.environ.get("AI_ASSISTANT_MAX_TOKENS", "700"))
AI_ASSISTANT_MAX_MESSAGE_LENGTH = int(os.environ.get("AI_ASSISTANT_MAX_MESSAGE_LENGTH", "1000"))
AI_ASSISTANT_MAX_HISTORY = int(os.environ.get("AI_ASSISTANT_MAX_HISTORY", "6"))
AI_ASSISTANT_RATE_LIMIT = int(os.environ.get("AI_ASSISTANT_RATE_LIMIT", "15"))

_raw_assistant_enabled = os.environ.get("AI_ASSISTANT_ENABLED")
if _raw_assistant_enabled is None or _raw_assistant_enabled.strip() == "":
    AI_ASSISTANT_ENABLED = bool(AI_API_KEY)
else:
    AI_ASSISTANT_ENABLED = _raw_assistant_enabled.strip().lower() in (
        "true",
        "1",
        "yes",
    )

# Алиасы для обратной совместимости
OPENAI_API_KEY = AI_API_KEY
OPENAI_MODEL = AI_MODEL

# Настройки Web Push (VAPID)
PUSH_VAPID_PUBLIC_KEY = os.environ.get("PUSH_VAPID_PUBLIC_KEY", "").strip()
PUSH_VAPID_PRIVATE_KEY = os.environ.get("PUSH_VAPID_PRIVATE_KEY", "").strip()
PUSH_VAPID_CLAIMS_EMAIL = os.environ.get("PUSH_VAPID_CLAIMS_EMAIL", "mailto:admin@kyrgyzaltyn.kg").strip()
