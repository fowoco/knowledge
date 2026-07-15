.PHONY: venv install validate test check

PYTHON ?= .venv/bin/python
BOOTSTRAP_PYTHON ?= python3.11

venv:
	$(BOOTSTRAP_PYTHON) -m venv .venv

install:
	$(PYTHON) -m pip install -e "./fowoco-knowledge[dev]"

validate:
	$(PYTHON) -m fowoco_knowledge validate

test:
	$(PYTHON) -m pytest fowoco-knowledge/tests

check: validate test
