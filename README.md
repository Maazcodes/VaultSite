# Vault Site

Prototype Django UI for the Vault digital preservation service.

## Requirements and Installation

- Python 3.8
- Create a virtual env
- Install requirements.txt (Django 3.2 and Jinja2)
- Set DJANGO_SECRET_KEY environment variable (or app will fail to start)
- Hot links some CSS from the production AIT partner site, as possible,
  and see below for handling the special case of the admin page (!?!?)
- Create a local sqlite with `manage.py migrate`
- Create initial user with `manage.py createsuperuser`
- Collect static files (css and js) with 'python3 manage.py collectstatic'
- Link static files dir into Apache root: ln -s .../static .../django-admin-static-hack
- And then add Apache config clause as doc'd here:
  https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/modwsgi/#serving-files
- Log in to admin
- Create an organization and associate your user with that org

## Todo

- Configure REMOTE_USER support
- Login page with REMOTE_USER support
- Oh you know, actually upload files (current view left unfinished)
- All production configuration
