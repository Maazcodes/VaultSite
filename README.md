# Vault Site
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Prototype Django UI for the Vault digital preservation service.

## Requirements and Installation

### Docker-Dev Install

See https://git.archive.org/archive-it/docker-dev#vault-site-development-quick-start

Use Docker-Dev for a quicker setup.

### Virtualenv + Docker Install
- Python 3.8
- Run Postgres, install into virtual environment, and start the app:
```
cd path/to/project
utilities/dev-postgres.sh start
make migrate
AIT_CONF=./DPS_dev/vault.yml ./venv/bin/python manage.py createsuperuser
REMOTE_USER=<your-superuser-name> make run
# in a separate shell:
make test
```

### If under Apache
- Collect static files (css and js) with 'python3 manage.py collectstatic'
- Link static files dir into Apache root: ln -s .../static .../django-admin-static-hack
- And then add Apache config clause as doc'd here:
  https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/modwsgi/#serving-files

### Finally
- Log in to [admin](http://localhost:8000/admin/)
- Create a plan, an organization and associate your user with that org
- From the [dashboard](http://localhost:8000/dashboard), create a collection
- Deposit file(s) to your new collection

### Regarding `REMOTE_USER`
Until we complete de-apachefication we are using Apache `REMOTE_USER`
authentication. Django inspects the `REMOTE_USER` env var and looks up that
username in its vault_user table. As such, above, we set the `REMOTE_USER`
environment variable to the username of the superuser we created.

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
