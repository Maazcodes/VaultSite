# Vault Site

Prototype Django UI for the Vault digital preservation service.

## Requirements and Installation

- Python 3.8
- Create a virtual env
- Install requirements.txt (Django 3.2 and Jinja2)
- Set DJANGO_SECRET_KEY environment variable (or app will fail to start)
- Hot links some CSS from the production AIT partner site
- Create a local sqlite with `manage.py migrate`
- Create initial user with `manage.py createsuperuser`
- Log in to admin
- Create an organization and associate your user with that org

## Todo

- Configure REMOTE_USER support
- Login page with REMOTE_USER support
- Oh you know, actually upload files (current view left unfinished)
- All production configuration