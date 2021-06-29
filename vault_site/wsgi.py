"""
WSGI config for vault_site project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vault_site.settings')
#os.environ['DJANGO_SETTINGS_MODULE'] = 'vault_site.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

#from django.contrib.auth.handlers.modwsgi import check_password, groups_for_user
