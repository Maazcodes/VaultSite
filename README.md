# Vault Site

Prototype Django UI for the Vault digital preservation service.

## Requirements and Installation

- Python 3.8
- Create a virtual env
- Install requirements.txt (Django 3.2 and Jinja2)
- Set a secret key in `/etc/_django_secret_key_vault_` (or app will fail to start)
- Set `DJANGO_SETTINGS_MODULE` to one of vault_site.settings.{local, production} 
- Create a local sqlite with `manage.py migrate`
- Create initial user with `manage.py createsuperuser`
  
### If under Apache
- Collect static files (css and js) with 'python3 manage.py collectstatic'
- Link static files dir into Apache root: ln -s .../static .../django-admin-static-hack
- And then add Apache config clause as doc'd here:
  https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/modwsgi/#serving-files

### Finally
- Log in to admin
- Create a plan, an organization and associate your user with that org

## Todo

- Login page with REMOTE_USER support
- All production configuration
- Should wsgi.py and asgi.py pick a different value for `os.environ.setdefault['DJANGO_SETTINGS_MODULE']`?
