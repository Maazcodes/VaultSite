PIPTOOLS_VERSION = "6.4.0"

DPS_DIR = ./DPS_dev
FILES_DPATH = $(DPS_DIR)/files
SHA_DPATH = $(DPS_DIR)/SHA_DIR
TMP_DPATH = $(DPS_DIR)/tmp
LOGFILE_DPATH = $(DPS_DIR)/logs
STATIC_ROOT_DPATH = $(DPS_DIR)/html/django-admin-static-hack
DEV_DIRS = \
		   $(STATIC_ROOT_DPATH) \
		   $(FILES_DPATH) \
		   $(LOGFILE_DPATH) \
		   $(SHA_DPATH) \
		   $(TMP_DPATH)

export AIT_CONF = $(DPS_DIR)/vault.yml

venv: requirements.dev.txt
	virtualenv venv
	venv/bin/pip install pip-tools==$(PIPTOOLS_VERSION)
	venv/bin/pip-sync requirements.dev.txt
	touch venv

$(DEV_DIRS):
	mkdir -p $@

$(AIT_CONF): $(DEV_DIRS)
	echo "FILE_UPLOAD_TEMP_DIR: $(TMP_DPATH)" > $@
	echo "LOGFILE_PATH: $(LOGFILE_DPATH)/django-debug.log" >> $@
	echo "MEDIA_ROOT: $(FILES_DPATH)" >> $@
	echo "SHADIR_ROOT: $(SHA_DPATH)" >> $@
	echo "STATIC_ROOT: $(STATIC_ROOT_DPATH)" >> $@

.PHONY: test
test: venv $(AIT_CONF)
	venv/bin/pytest

.PHONY: migrate
migrate: venv $(AIT_CONF)
	venv/bin/python manage.py migrate

.PHONY: run
run: venv $(AIT_CONF)
ifndef REMOTE_USER
	@echo "ensure REMOTE_USER is set and try again"
	@exit 1
endif
	venv/bin/python ./utilities/process_chunked_files.py & venv/bin/python manage.py runserver

.PHONY: clean
clean:
	rm -rf $(DPS_DIR)
	rm -rf venv
	rm -rf postgres-data
