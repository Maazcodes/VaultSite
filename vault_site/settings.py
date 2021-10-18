"""
Django settings for vault_site project.

Generated by 'django-admin startproject' using Django 3.2.3.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

import os
import yaml
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

MEDIA_ROOT = Path("/opt/DPS/files/")

SHADIR_ROOT = Path("/opt/DPS/SHA_DIR/")

FILE_UPLOAD_TEMP_DIR = Path("/opt/DPS/tmp/")

# LOGIN_REDIRECT_URL = '/dashboard'

EMAIL_HOST = "mail.archive.org"

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

conf = {}
with open(os.environ.get("AIT_CONF", "/etc/vault.yml")) as f:
    conf = yaml.safe_load(f)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = conf.get(
    "SECRET_KEY",
    "devsecretkeyljkadfadfsjkl9ew0f02iefj20h8310hknsnlasd172yo1lnimposimfn",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = conf.get("DEBUG", True)

DEPLOYMENT_ENVIRONMENT = conf.get("DEPLOYMENT_ENVIRONMENT", "DEV")

IA_CONFIG_PATH = conf.get("IA_CONFIG_PATH")

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "wbgrp-svc600.us.archive.org",
    "207.241.235.20",
    "207.241.225.89",
    "avdempsey-dev.us.archive.org",
    "adam-dev.us.archive.org",
    "wbgrp-svc018.us.archive.org",
    "wbgrp-vault-site-qa.us.archive.org",
]

# Allow registration of large Deposits in single request
# TODO: chunk deposit registration so we can cap POST size
DATA_UPLOAD_MAX_MEMORY_SIZE = None  # Defaults to 2.5MB

FILE_UPLOAD_HANDLERS = [
    #'django.core.files.uploadhandler.MemoryFileUploadHandler',
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "vault.apps.VaultConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.RemoteUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "vault_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "environment": "vault_site.jinja2env.environment",
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "vault.context_processors.sentry_dsn",
            ],
        },
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
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

WSGI_APPLICATION = "vault_site.wsgi.application"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.RemoteUserBackend",
    # "django.contrib.auth.backends.ModelBackend",
]

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": conf.get("VAULT_POSTGRES_NAME", "vault"),
        "USER": conf.get("VAULT_POSTGRES_USER", "vault"),
        "PASSWORD": conf.get("VAULT_POSTGRES_PASSWORD", "vault"),
        "HOST": conf.get("VAULT_POSTGRES_HOST", "127.0.0.1"),
        "PORT": conf.get("VAULT_POSTGRES_PORT", "5432"),
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
}


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/vault/static/"
STATICFILES_DIRS = [
    BASE_DIR / "vault/static/",
]

# STATIC_ROOT = BASE_DIR / 'vault/static'

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "vault.User"

LOGIN_URL = "/vault/accounts/login/"

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

SENTRY_DSN = conf.get("SENTRY_DSN", "")

sentry_sdk.init(
    dsn=SENTRY_DSN,
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=True,
    environment=DEPLOYMENT_ENVIRONMENT,
)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "/opt/DPS/vault-site/django-debug.log",
            # 'maxBytes': 1024*1024*100,
            # 'backupCount': 100,
            "formatter": "plain",
        },
    },
    "root": {
        "handlers": ["file"],
        "level": "INFO",
    },
    "loggers": {
        "vault": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
