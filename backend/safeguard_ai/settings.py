
import os
from pathlib import Path
from datetime import timedelta
import sentry_sdk
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY') or 'unsafe-dev-key'
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', 'localhost').split(',') if host.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'apps.citizens',
    'apps.hazards',
    'apps.alerts',
    'apps.rescue',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'safeguard_ai.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {'context_processors': [
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ]},
    },
]

WSGI_APPLICATION = 'safeguard_ai.wsgi.application'
ASGI_APPLICATION = 'safeguard_ai.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('DATABASE_NAME', 'safeguard_ai'),
        'USER': os.getenv('DATABASE_USER', 'postgres'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD', 'November2002'),
        'HOST': os.getenv('DATABASE_HOST', 'localhost'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
}

default_cors_origins = 'http://localhost:3000,http://127.0.0.1:3000,http://0.0.0.0:3000'
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CORS_ALLOWED_ORIGINS', default_cors_origins).split(',')
    if origin.strip()
]

default_cors_origin_regexes = r'^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$'
CORS_ALLOWED_ORIGIN_REGEXES = [
    pattern.strip()
    for pattern in os.getenv('CORS_ALLOWED_ORIGIN_REGEXES', default_cors_origin_regexes).split(',')
    if pattern.strip()
]
CORS_ALLOW_CREDENTIALS = True

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    'ingest-hazard-data-every-30-minutes': {
        'task': 'apps.hazards.tasks.ingest_hazard_data_task',
        'schedule': 60 * 30,
    },
    'send-periodic-risk-updates-every-hour': {
        'task': 'apps.alerts.tasks.send_periodic_risk_updates_task',
        'schedule': 60 * 60,
    }
}

SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.2, profiles_sample_rate=0.2)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
GEMINI_RATE_LIMIT_MINUTES = int(os.getenv('GEMINI_RATE_LIMIT_MINUTES', '60'))

# Groq — free tier, used exclusively for the chatbot (protects Gemini quota)
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
KMD_API_URL = os.getenv('KMD_API_URL', '')
KMD_API_KEY = os.getenv('KMD_API_KEY', '')
NOAA_API_URL = os.getenv('NOAA_API_URL', '')
NOAA_API_KEY = os.getenv('NOAA_API_KEY', '')
OPEN_METEO_API_URL = os.getenv('OPEN_METEO_API_URL', 'https://api.open-meteo.com/v1/forecast')
OPEN_METEO_POINTS = os.getenv('OPEN_METEO_POINTS', '')
HAZARD_MAX_ITEMS_PER_RUN = os.getenv('HAZARD_MAX_ITEMS_PER_RUN', '80')
HAZARD_ALERT_DEDUP_MINUTES = os.getenv('HAZARD_ALERT_DEDUP_MINUTES', '30')

AFRICASTALKING_USERNAME = os.getenv('AFRICASTALKING_USERNAME', '')
AFRICASTALKING_API_KEY = os.getenv('AFRICASTALKING_API_KEY', '')
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

# Keep GDAL path optional for cross-platform compatibility. GeoDjango will attempt
# automatic discovery unless GDAL_LIBRARY_PATH is explicitly provided in the env.
GDAL_LIBRARY_PATH = os.getenv('GDAL_LIBRARY_PATH')

# Redis cache configuration for django-redis
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

