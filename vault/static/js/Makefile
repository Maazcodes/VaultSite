.PHONY: lint
lint: node_modules
	yarn run lint

.PHONY: format
format: node_modules
	# TODO: Make sure prettier doesn't make multiline html string formatting
	# worse:
	# @Mike Wilson, when you  when you run prettier on the web component files,
	# it's gonna do ugly stuff to the embedded multi-line HTML strings.
	# prettier does support proper formatting of html tagged templates, so I've
	# hacked my way into this feature in the partner-site using this dummy html
	# template function (example usage and prettier result). (edited)
	# see: https://internetarchive.slack.com/archives/C02DPK2TKQT/p1646764411485789
	yarn run format

.PHONY: ck-format
ck-format: node_modules
	yarn run ck-format

node_modules: package.json yarn.lock
	yarn install
