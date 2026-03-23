.PHONY: install lint test run

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests
	python -m mypy

test:
	python -m pytest

run:
	flask --app legaldesk.web.app run --debug
