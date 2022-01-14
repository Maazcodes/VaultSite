from .settings import *


TEST_FIXTURE_USER = "tester"
os.environ["REMOTE_USER"] = TEST_FIXTURE_USER

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": conf.get("VAULT_TEST_POSTGRES_NAME", "vault"),
        "USER": conf.get("VAULT_TEST_POSTGRES_USER", "vault"),
        "PASSWORD": conf.get("VAULT_TEST_POSTGRES_PASSWORD", "vault"),
        "HOST": conf.get("VAULT_TEST_POSTGRES_HOST", "127.0.0.1"),
        "PORT": conf.get("VAULT_TEST_POSTGRES_PORT", "5432"),
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
}
