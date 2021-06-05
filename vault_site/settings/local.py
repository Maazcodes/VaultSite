from .base import *

AUTHENTICATION_BACKENDS = [
        'django.contrib.auth.backends.RemoteUserBackend',
        'django.contrib.auth.backends.ModelBackend',
        ]
