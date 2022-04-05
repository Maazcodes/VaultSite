from django.conf import settings


def sentry_dsn(request):
    return {
        "SENTRY_DSN": settings.SENTRY_DSN,
    }


def vault_version(request):
    return {
        "VAULT_VERSION": settings.VAULT_VERSION,
        "VAULT_GIT_COMMIT_HASH": settings.VAULT_GIT_COMMIT_HASH,
    }
