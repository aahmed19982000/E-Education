"""
Django settings for the E-Education Academy project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Falls back to the dev-only key below so local `runserver` keeps working
# unchanged; set DJANGO_SECRET_KEY before deploying anywhere reachable.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-kaa8i3wq585$^x0zl^@ba0(+!!88_5(32*c!4dp&2wl=qgrfod',
)

# Both default to today's dev-friendly values so local `runserver` is
# unaffected; override with real env vars when deploying anywhere reachable.
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# HTTPS-only hardening: off by default (plain http:// dev server, or a
# deployment not yet behind TLS); set DJANGO_USE_HTTPS=True once the site is
# served over real HTTPS (e.g. Nginx + a certificate), or this redirects
# every request to a https:// port nothing is listening on.
USE_HTTPS = os.environ.get('DJANGO_USE_HTTPS', 'False').lower() == 'true'
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS
SECURE_SSL_REDIRECT = USE_HTTPS
SECURE_HSTS_SECONDS = 31536000 if USE_HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = USE_HTTPS
SECURE_HSTS_PRELOAD = USE_HTTPS


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'core',
    'levels',  # migrations only: quiz/courses migrations depend on it
    'articles',
    'team',
    'quiz',
    'courses',
    'accounts',
    'contact_us',
    'dashboard',
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
    'core.middleware.LanguageMiddleware',
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
                'core.context_processors.site_language',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Defaults to local SQLite so `runserver` needs no setup; set DJANGO_DB_NAME
# (plus USER/PASSWORD/HOST/PORT) to switch to PostgreSQL in production.
if os.environ.get('DJANGO_DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['DJANGO_DB_NAME'],
            'USER': os.environ.get('DJANGO_DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DJANGO_DB_PASSWORD', ''),
            'HOST': os.environ.get('DJANGO_DB_HOST', 'localhost'),
            'PORT': os.environ.get('DJANGO_DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Added to local numbers (leading 0) when building wa.me links; Egypt by default.
WHATSAPP_DEFAULT_COUNTRY_CODE = os.environ.get('WHATSAPP_DEFAULT_COUNTRY_CODE', '20')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'ar'

TIME_ZONE = 'Africa/Cairo'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
# Files only enrolled students may download (never served via MEDIA_URL).
PRIVATE_MEDIA_ROOT = BASE_DIR / 'private_media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'core:home'

# Site brand colors (kept here so templates/static can stay in sync with the
# original design without hard-coding hex values in more than one place).
BRAND_PRIMARY_COLOR = '#14275B'
BRAND_ACCENT_COLOR = '#D9A429'

# Flip to True once a payment gateway (Daftar Cash / Binance Pay) is wired into the checkout.
PAYMENTS_ENABLED = os.environ.get('PAYMENTS_ENABLED', 'False').lower() == 'true'
