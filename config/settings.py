"""
Django settings for Avtomaktab to'lov tizimi.
"""

from pathlib import Path
from decouple import Config, RepositoryEnv, config as decouple_config

BASE_DIR = Path(__file__).resolve().parent.parent

env_file = BASE_DIR / '.env'
config = Config(RepositoryEnv(str(env_file))) if env_file.exists() else decouple_config

SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-me')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = [h.strip() for h in config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',') if h.strip()]

CENTER_NAME = config('CENTER_NAME', default='Avtomaktab')

ALLOWED_HOSTS = ['turon.33x.uz', 'www.turon.33x.uz', '189.74.100.15']

# Statik fayllarni yig'ish uchun:
STATIC_URL = '/static/'
STATIC_ROOT = '/var/www/turon_project/static'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    'django_htmx',

    'apps.core',
    'apps.accounts',
    'apps.groups',
    'apps.students',
    'apps.payments',
    'apps.lessons',
    'apps.expenses',
    'apps.notifications',
    'apps.reports',
    'apps.site_settings',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'apps.core.middleware.CurrentUserMiddleware',
    'apps.core.middleware.BlockedUserMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
DB_DIR = Path(config('DB_DIR', default=str(BASE_DIR)))
DB_DIR.mkdir(parents=True, exist_ok=True)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DB_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 5,
        },
    }
}

AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.PhoneBackend',
]

# Password hashing: Argon2 first, per texnik topshiriq
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

# Login rate limiting (5 ta noto'g'ri urinishdan keyin 15 daqiqa bloklash)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15


# Internationalization
LANGUAGE_CODE = 'uz'
TIME_ZONE = config('TIME_ZONE', default='Asia/Tashkent')
USE_I18N = True
USE_TZ = True


# Static & media files
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        # Production'da (DEBUG=False) `collectstatic` manifestidan foydalaniladi;
        # DEBUG/test paytida oddiy storage — manifest talab qilmaydi.
        'BACKEND': (
            'whitenoise.storage.CompressedManifestStaticFilesStorage'
            if not DEBUG else 'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'data' / 'uploads'

MAX_UPLOAD_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_UPLOAD_IMAGE_TYPES = ['image/jpeg', 'image/png']

BACKUP_DIR = Path(config('BACKUP_DIR', default=str(BASE_DIR / 'backups')))
BACKUP_KEEP_COUNT = 30

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Security
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# nginx orqali kelganda to'g'ri sxema (http/https) aniqlansin (X-Forwarded-Proto)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ENABLE_SSL: domen + TLS sertifikati sozlanganda True qiling (.env). Hozircha
# faqat IP/HTTP orqali ishga tushirilsa, False qoldiring — aks holda nginx hali
# 443-portda xizmat qilmagani uchun cheksiz redirect yuzaga keladi.
ENABLE_SSL = config('ENABLE_SSL', default=False, cast=bool)

if not DEBUG and ENABLE_SSL:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# CORS: hozircha kerak emas — frontend Django shablonlari orqali bir xil origin'da
# ishlaydi. Agar kelgusida alohida frontend/mobil ilova qo'shilsa, `django-cors-headers`
# o'rnatilib, shu yerga CORS_ALLOWED_ORIGINS qo'shiladi.

# Logging: structured (JSON), errors in a separate file
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'apps.core.logging_utils.JsonFormatter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'app_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'app.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'json',
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'errors.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'level': 'ERROR',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console', 'app_file', 'error_file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'app_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# APScheduler: faqat bitta worker'da ishga tushirilsin
RUN_SCHEDULER = config('RUN_SCHEDULER', default=True, cast=bool)
