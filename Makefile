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

venv:
	virtualenv venv

./venv/bin/pip-sync: venv
	venv/bin/pip install pip-tools==$(PIPTOOLS_VERSION)
	touch $@

requirements.txt: requirements.in ./venv/bin/pip-sync
	venv/bin/pip-compile --output-file $@ $<

requirements.test.txt: requirements.test.in requirements.txt
	venv/bin/pip-compile --output-file $@ $<

requirements.dev.txt: requirements.dev.in requirements.test.txt
	venv/bin/pip-compile --output-file $@ $<
	venv/bin/pip-sync $@

$(DEV_DIRS):
	mkdir -p $@

$(AIT_CONF): $(DEV_DIRS)
	@echo "FILE_UPLOAD_TEMP_DIR: $(TMP_DPATH)" > $@
	@echo "MEDIA_ROOT: $(FILES_DPATH)" >> $@
	@echo "SHADIR_ROOT: $(SHA_DPATH)" >> $@
	@echo "STATIC_ROOT: $(STATIC_ROOT_DPATH)" >> $@
	@echo "PETABOX_SECRET: bogus-petabox-secret" >> $@

.PHONY: test
test: requirements.dev.txt $(AIT_CONF)
	@# pass extra params on to pytest: https://stackoverflow.com/a/6273809
	venv/bin/pytest $(filter-out $@,$(MAKECMDGOALS))

.PHONY: migrate
migrate: requirements.dev.txt $(AIT_CONF)
	venv/bin/python manage.py migrate

.PHONY: run
run: requirements.dev.txt $(AIT_CONF)
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
	find . -name "__pycache__" -exec rm -rf "{}" +
