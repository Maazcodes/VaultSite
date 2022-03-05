import os

from .settings import *


TEST_FIXTURE_USER = "tester"
os.environ["HTTP_REMOTE_USER"] = TEST_FIXTURE_USER

VAULT_TEST_POSTGRES_NAME = os.environ.get("VAULT_POSTGRES_NAME", "vault")
VAULT_TEST_POSTGRES_USER = os.environ.get("VAULT_POSTGRES_USER", "vault")
VAULT_TEST_POSTGRES_PASSWORD = os.environ.get("VAULT_POSTGRES_PASSWORD", "vault")
VAULT_TEST_POSTGRES_HOST = os.environ.get("VAULT_POSTGRES_HOST", "127.0.0.1")
VAULT_TEST_POSTGRES_PORT = os.environ.get("VAULT_POSTGRES_PORT", "5432")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": VAULT_TEST_POSTGRES_NAME,
        "USER": VAULT_TEST_POSTGRES_USER,
        "PASSWORD": VAULT_TEST_POSTGRES_PASSWORD,
        "HOST": VAULT_TEST_POSTGRES_HOST,
        "PORT": VAULT_TEST_POSTGRES_PORT,
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
}

PETABOX_SECRET = bytes("bogus-petabox-secret", "ascii")
