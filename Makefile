PIPTOOLS_VERSION = "6.5.1"
PYTHON_VERSION = 3.8

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
VAULT_SITE_EGG_LINK = ./venv/lib/python$(PYTHON_VERSION)/site-packages/vault.egg-link
# where's the Makefile running? Valid options: LOCAL, CI
ENV ?= LOCAL
PYTEST_REPORT ?= pytest.xml
PYLINT_REPORT ?= pylint.json
MD_FILES = $(shell \
	grep \
	--perl-regexp \
	--files-with-matches \
	--include='*.md' \
	--dereference-recursive \
	'<!--\s+toc\s+-->' \
	. \
)

export AIT_CONF = $(DPS_DIR)/vault.yml

venv:
	python -m venv venv

./venv/bin/pip-sync: venv
	venv/bin/pip install pip-tools==$(PIPTOOLS_VERSION)
	touch $@

requirements.txt: requirements.in ./venv/bin/pip-sync
	venv/bin/pip-compile --output-file $@ $<

requirements.test.txt: requirements.test.in requirements.txt
	venv/bin/pip-compile --output-file $@ $<

requirements.dev.txt: requirements.dev.in requirements.test.txt
	venv/bin/pip-compile --output-file $@ $<

$(VAULT_SITE_EGG_LINK): venv setup.py
	venv/bin/pip install --editable .

.PHONY: setup
setup: ./venv/bin/pip-sync
ifeq ($(ENV),LOCAL)
	$< requirements.dev.txt
else ifeq ($(ENV),CI)
	$< requirements.test.txt
endif

$(DEV_DIRS):
	mkdir -p $@

$(AIT_CONF): $(DEV_DIRS)
	@echo "FILE_UPLOAD_TEMP_DIR: $(TMP_DPATH)" > $@
	@echo "MEDIA_ROOT: $(FILES_DPATH)" >> $@
	@echo "SHADIR_ROOT: $(SHA_DPATH)" >> $@
	@echo "STATIC_ROOT: $(STATIC_ROOT_DPATH)" >> $@
	@echo "PETABOX_SECRET: bogus-petabox-secret" >> $@

.git/hooks/pre-commit:
	ln -s $(realpath ./dev/pre-commit) $@

.PHONY: test
test: $(VAULT_SITE_EGG_LINK) $(AIT_CONF)
ifeq ($(ENV),LOCAL)
	@# pass extra params on to pytest: https://stackoverflow.com/a/6273809
	venv/bin/pytest $(filter-out $@,$(MAKECMDGOALS))
else ifeq ($(ENV),CI)
	venv/bin/pytest \
		--junit-xml=$(PYTEST_REPORT) \
		--cov=vault \
		--cov=vault_site \
		--cov-report=xml
endif

.PHONY: lint
lint: $(VAULT_SITE_EGG_LINK) $(AIT_CONF)
ifeq ($(ENV),LOCAL)
	venv/bin/pylint vault vault_site
else ifeq ($(ENV),CI)
	venv/bin/pylint vault vault_site \
		--output-format=pylint_gitlab.GitlabCodeClimateReporter \
		--reports=y > $(PYLINT_REPORT)
endif

.PHONY: format
format: $(VAULT_SITE_EGG_LINK) $(AIT_CONF)
	venv/bin/black .

.PHONY: ck-format
ck-format: $(VAULT_SITE_EGG_LINK) $(AIT_CONF)
	venv/bin/black --check .

.PHONY: migrate
migrate: $(VAULT_SITE_EGG_LINK) $(AIT_CONF)
	venv/bin/python manage.py migrate

.PHONY: run
run: $(VAULT_SITE_EGG_LINK) $(AIT_CONF)
	venv/bin/python ./vault/utilities/process_chunked_files.py & venv/bin/python manage.py runserver

# generates tables of contents in markdown files. To opt in, make sure your
# file matches the glob *.md, and then add `<!-- toc -->` to the document in
# the spot you'd like the ToC to appear.
.PHONY: md-toc
md-toc: $(MD_FILES)
	for fname in $^; do npx markdown-toc -i $$fname; done

.PHONY: clean
clean:
	rm -rf $(DPS_DIR)
	rm -rf venv
	rm -rf postgres-data
	find . -name "__pycache__" -exec rm -rf "{}" +
