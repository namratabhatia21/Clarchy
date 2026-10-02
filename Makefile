.PHONY: install test lint format examples check prices site

install:
	pip install -e ".[dev]"

test:
	python -m pytest -q

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

# Regenerates examples/, which double as golden files for the tests.
examples:
	UPDATE_GOLDEN=1 python -m pytest -q tests/test_render.py

check: lint test

# The public site, built the same way by the Pages workflow and by Cloudflare Workers
# Builds (build command: make prices site). It uses its own virtual environment in build/,
# so it works with any Python 3.11+ on the PATH.
PYTHON ?= python3
SITE_VENV := build/site-venv

$(SITE_VENV):
	$(PYTHON) -m venv $(SITE_VENV)

# Refreshes the AWS price book from the AWS Price List API, and keeps the committed one
# when the API can't be reached.
prices: $(SITE_VENV)
	$(SITE_VENV)/bin/pip install -q pyyaml
	PYTHONPATH=src $(SITE_VENV)/bin/python -m clarchy.aws_prices \
		--output src/clarchy/data/prices/aws.yaml \
		|| echo "warning: could not refresh AWS prices; using the committed price book"

# site/index.html and site/clarchy-engine.zip, served as static assets (wrangler.jsonc).
site: $(SITE_VENV)
	$(SITE_VENV)/bin/pip install -q .
	$(SITE_VENV)/bin/python -m clarchy.cli export-site -o site
