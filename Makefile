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

# Refreshes the price books from the providers' price APIs, for every region, when
# CLARCHY_REFRESH_PRICES=1 (the daily workflow, .github/workflows/prices.yml, sets it and
# commits the result). Otherwise the committed books are used, so site builds stay fast.
# A provider whose API can't be reached keeps its committed book.
prices: $(SITE_VENV)
ifeq ($(CLARCHY_REFRESH_PRICES),1)
	$(SITE_VENV)/bin/pip install -q pyyaml
	PYTHONPATH=src $(SITE_VENV)/bin/python -m clarchy.aws_prices \
		--output src/clarchy/data/prices/aws.yaml \
		|| echo "warning: could not refresh AWS prices; using the committed price book"
else
	@echo "prices: using the committed price books (CLARCHY_REFRESH_PRICES=1 refreshes them)"
endif

# site/index.html and site/clarchy-engine.zip, served as static assets (wrangler.jsonc).
site: $(SITE_VENV)
	$(SITE_VENV)/bin/pip install -q .
	$(SITE_VENV)/bin/python -m clarchy.cli export-site -o site
