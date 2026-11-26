from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Secrets and debug come from the environment; the fallbacks are for local development only.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-artstock-dev-only-change-me')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'stock.apps.StockConfig',
    'django.contrib.admin',
    'django_prometheus',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'artstock.middleware.NoCacheForMetricsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'artstock.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'stock' / 'template'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'stock.context_processors.cart_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'artstock.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_DB_PATH', BASE_DIR / 'db.sqlite3'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Redis is used when REDIS_URL is set (docker-compose sets it); otherwise an
# in-process cache keeps the site working without a Redis server.
REDIS_URL = os.environ.get('REDIS_URL')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
        }
    }
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

STATIC_URL = '/s/'
STATICFILES_DIRS = [BASE_DIR / 'stock' / 'template' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'stock.User'

LOGIN_URL = 'login_customer'
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
