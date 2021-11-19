# Vault Site
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Prototype Django UI for the Vault digital preservation service.

## Requirements and Installation

- Python 3.8
- Optionally pip-tools
- Create **/etc/vault.yml** for all config referenced in vault_site/settings.py
- Run Postgres, install into virtual environment, and start the app:
```
cd path/to/project
mkdir postgres-data
docker run --name vault-postgres -v postgres-data:/var/lib/postgresql/data \
    -p 5432:5432 \
    -e POSTGRES_USER=vault -e POSTGRES_PASSWORD=vault \
    -d postgres:10
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# or if you have pip-tools
# pip-sync requirements.txt requirements.test.txt requirements.dev.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
- Run tests: pytest
  
### If under Apache
- Collect static files (css and js) with 'python3 manage.py collectstatic'
- Link static files dir into Apache root: ln -s .../static .../django-admin-static-hack
- And then add Apache config clause as doc'd here:
  https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/modwsgi/#serving-files

### Finally
- Log in to admin
- Create a plan, an organization and associate your user with that org