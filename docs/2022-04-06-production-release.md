# 2022 April 06 Production Release Change Management Document

<!-- toc -->

- [Overview](#overview)
- [Procedure](#procedure)

<!-- tocstop -->

## Overview

On 06 April 2022 Vault is being deployed to production for the first time after
a lengthy lapse in deployments. This document describes the planned deployment
procedure.

* **Release runner**: Mike Wilson
* **Deployment schedule**: 06 April 2022 at 1 PM PDT
* **Affected Infrastructure**: vault-site production (`wbgrp-svc600`)

## Procedure

- [x] 0. announce the forthcoming deployment in `#vault`
- [x] 1. stop, disable and uninstall apache2
  ```sh
  sudo systemctl stop apache2
  sudo systemctl disable apache2
  TODO: sudo apt remove apache2
  ```
- [x] 2. uninstall snap certbot (LetsEncrypt) client and clear state
  ```sh
  sudo snap remove certbot
  sudo rm -rf /etc/letsencrypt
  ```
- [x] 3. stop and disable daemontools-managed uploader processor scripts
  ```sh
  sudo svc -d /etc/service/process_hashed_files
  sudo svc -d /etc/service/process_chunked_files
  sudo rm -rf /etc/service/process*
  ```
- [x] 4. uninstall daemontools
  ```sh
  sudo apt remove daemontools daemontools-run
  ```
- [x] 5. deploy vault (from mwilson-dev)
  ```sh
  ansible-playbook --ask-vault-password -i prod setup_vault_site.yml --extra-vars git_ref=releases/2022-04-06
  ```
- [x] 6. disable vault app server
  ```sh
  sudo systemctl stop gunicorn
  ```
- [x] 7. run DB migrations
  ```sh
  sudo /opt/DPS/venv/bin/python3 /opt/DPS/vault-site/manage.py migrate
  ```
- [x] 8. set Django-auth passwords for all users
  ```sh
  # first, copy passwords file onto prod app server, e.g.:
  # scp user-pass.csv wbgrp-svc600:~/
  sudo /opt/DPS/venv/bin/python3 /opt/DPS/vault-site/manage.py bulk_change_passwords <user-pass-csv>
  ```
  - user `bigwheel` did not exist
  - user `natlArcJ` did not exist
  - **TODO**: we should modify the bulk user password update script to print names of nonexistent users
- [x] 9. recalculate TreeNode accounting for existing records
  ```sh
  # first, attempt a dry run:
  sudo /opt/DPS/venv/bin/python3 /opt/DPS/vault-site/manage.py recalculate_treenode_accounting

  # then, actually store the recalculated TreeNode accounting:
  sudo /opt/DPS/venv/bin/python3 /opt/DPS/vault-site/manage.py recalculate_treenode_accounting --no-dry-run
  ```
- [x] 10. re-enable vault app server
  ```sh
  sudo systemctl start gunicorn
  ```
- [x] 11. spot-check production web GUI for general healthiness:
  https://wbgrp-svc600.us.archive.org/vault/
- [x] 12. announce the outcome of the deployment in `#vault`
