PY ?= python3

.PHONY: help check validate catalog site test vendor-status vendor-sync vendor-update verify refs-update refs-serve image

help: ## list targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

check: validate test ## what CI runs offline: validate, tests, catalog drift
	$(PY) tools/catalog.py --check

validate: ## lint skills (spec + authoring rules)
	$(PY) tools/validate.py --strict

catalog: ## regenerate the README catalog block
	$(PY) tools/catalog.py

site: ## build the Pages site into _site/ (queries upstream)
	$(PY) tools/catalog.py --site _site --upstream

test: ## unit tests
	$(PY) -m unittest discover -s tests -v

vendor-status: ## pinned vs upstream HEAD
	$(PY) tools/vendor.py status

vendor-sync: ## re-materialize vendored skills at their pins
	$(PY) tools/vendor.py sync

vendor-update: ## move pins to upstream HEAD, write upstream-report.md
	$(PY) tools/vendor.py sync --update --report upstream-report.md

verify: ## vendored skills are byte-identical to upstream
	$(PY) tools/vendor.py verify

refs-update: ## local reference index: clone corpora and build
	$(PY) skills/dev-references/scripts/refs.py update

refs-serve: ## run the refs MCP server locally (needs: pip install -r refs/requirements.txt)
	$(PY) refs/server.py

image: ## build the refs server image
	docker build -f refs/Dockerfile -t agent-skills-refs .
