# Development release notes

This document captures notes and actions that are required for the next
production release. This could include:

* migrations that need running
* special consideration regarding migrations (e.g., we need to temporarily
  disable app servers)
* manual steps
* risks


## Next release (May 2022)

* run migrations to pick up [`vault migrations 0037_unlimited_treenode_pbox_path_size py`](../vault/migrations/0037_unlimited_treenode_pbox_path_size.py)
    * (mwilson) I'd recommend shutting down the app server and both
      `process_chunked_files.py` and `process_hashed_files.py` while this
      migration runs
        * `sudo systemctl stop gunicorn`
        * `sudo systemctl stop process-hashed-files`
        * `sudo systemctl stop process-chunked-files`

## Previous releases

> Each time we do a release, copy the *Next release* section into this
> section and change the date to the actual date of the release.
