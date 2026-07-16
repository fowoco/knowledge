.PHONY: venv install format lint validate test check

PYTHON ?= .venv/bin/python
BOOTSTRAP_PYTHON ?= python3.11

venv:
	$(BOOTSTRAP_PYTHON) -m venv .venv

install:
	$(PYTHON) -m pip install -e "./fowoco-knowledge[dev]"

format:
	$(PYTHON) -m ruff format fowoco-knowledge/src fowoco-knowledge/tests
	$(PYTHON) -m ruff check --fix fowoco-knowledge/src fowoco-knowledge/tests

lint:
	$(PYTHON) -m ruff format --check fowoco-knowledge/src fowoco-knowledge/tests
	$(PYTHON) -m ruff check fowoco-knowledge/src fowoco-knowledge/tests

validate:
	$(PYTHON) -m fowoco_knowledge validate

test:
	$(PYTHON) -m pytest fowoco-knowledge/tests

check: lint validate test
