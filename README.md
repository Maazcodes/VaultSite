# Vault Site

Vault digital preservation service.

## Development

### Docker-Dev Install

See https://git.archive.org/archive-it/docker-dev#vault-site-development-quick-start

Use Docker-Dev for a quicker setup.

### Virtualenv + Docker Install
- Python 3.8
- Run Postgres, install into virtual environment, and start the app:
```
cd path/to/project
utilities/dev-postgres.sh start
make setup
# set up git pre-commit hook; optional, but recommended
make .git/hooks/pre-commit
make migrate
AIT_CONF=./DPS_dev/vault.yml ./venv/bin/python manage.py createsuperuser
HTTP_REMOTE_USER=<your-superuser-name> make run
# in a separate shell:
make test
```

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
The project is using [pip-tools(https://github.com/jazzband/pip-tools) for
dependency management. To get things running it can be as simple as `pip
install -r requirements.dev.txt` but if you use `pip-sync requirements.dev.txt`
it will keep your virtualenv in sync with the pinned dependencies.

There are three sets of dependencies for three environments:
- requirements.txt (prod/qa/etc)
- requirements.test.txt (all the above plus deps for running tests)
- requirements.dev.txt (all the above plus deps for local development)

You only need to install one set of dependencies for the environment you're
running in. Each of these `.txt` files has a corresponding `.in` file. The
`.txt` files serve as the lock file including pinned versions of all transitive
dependencies.

### Adding new dependencies

- Add the name of the package to the corresponding `.in` file for the
  environment the dependency is appropriate for.
- Run `pip-compile` "inside out" from the environment you added the dep to.
  - E.g. when a dep is added to requirements.in run pip-compile on
    requirements.in, requirements.test.in, then requirements.dev.in
- Run `pip-sync` for the corresponding `.txt` file for the environment

## Deployment
Vault is deployed using
[ait-ansible](https://git.archive.org/archive-it/ait-ansible). So that we
always understand exactly what changes we're deploying, deployments must be
made targeting a specific git ref (i.e., a hash, tag, or branch name), which we
do using the `git_ref` ansible var. Example:

```sh
# - be ssh'd onto a machine in-cluster
# - have an up-to-date clone of ait-ansible

# from the ait-ansible directory
pwd
./git.archive.org/archive-it/ait-ansible

# git refs are provided via the `git_ref` var
ansible-playbook --ask-vault-password -i qa setup_vault_site.yml --extra-vars git_ref=eec824149cc850e094dd92921e4af0f8f13ee380
# ...
```
