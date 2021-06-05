from .base import *


AUTHENTICATION_BACKENDS = [
        'django.contrib.auth.backends.RemoteUserBackend',
        # 'django.contrib.auth.backends.ModelBackend',
        ]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/opt/DPS/vault-site/django-debug.log',
        },
    },
    'loggers': {
        'vault': {
            'handlers': ['file'],
            'level': 'INFO',
            'formatter': 'plain',
            'propagate': True,
        },
    },
}
