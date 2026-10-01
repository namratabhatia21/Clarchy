.PHONY: install test lint format examples check

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
