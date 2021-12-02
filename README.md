# Vault Site
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Prototype Django UI for the Vault digital preservation service.

## Requirements and Installation

### Docker-Dev Install

See https://git.archive.org/archive-it/docker-dev#vault-site-development-quick-start

Use Docker-Dev for a quicker setup.

### Virtualenv + Docker Install
- Python 3.8
- Optionally pip-tools
- Create **/etc/vault.yml** for all config referenced in vault_site/settings.py
- Create these dirs:
  - /opt/DPS/
    - SHA_DIR
    - files
    - html
    - tmp
    - vault-site
      - django-debug.log
- Set environment variable REMOTE_USER to your username of choice
  - Until we complete de-apachefication we are using Apache REMOTE_USER authentication.
  - Django inspects the REMOTE_USER env var and looks up that username in its vault_user table.
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
# for a local dev environment
# pip-sync requirements.dev.txt 
# for a prod environment
# pip-sync requirements.txt
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

## Dependency Management

The project is using pip-tools for dependency management. To get things running it can
be as simple as `pip install -r requirements.dev.txt` but if you use `pip-sync
requirements.dev.txt` it will keep your virtualenv in sync with the pinned dependencies.

There are three sets of dependencies for three environments:
- requirements.txt (prod/qa/etc)
- requirements.test.txt (all the above plus deps for running tests)
- requirements.dev.txt (all the above plus deps for local development)

You only need to install one set of dependencies for the environment you're running in.
Each of these `.txt` files has a corresponding `.in` file. The `.txt` files serve as the
lock file including pinned versions of all transitive dependencies.

### Adding new dependencies

- Add the name of the package to the corresponding `.in` file for the environment the
dependency is appropriate for.
- Run `pip-compile` "inside out" from the environment you added the dep to.
  - E.g. when a dep is added to requirements.in run pip-compile on requirements.in, 
requirements.test.in, then requirements.dev.in
- Run `pip-sync` for the corresponding `.txt` file for the environment

Adding a Makefile for all of this might not be a bad idea.
