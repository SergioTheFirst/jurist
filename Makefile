.PHONY: install lint test run check

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests
	python -m mypy

test:
	python -m pytest

run:
	flask --app legaldesk.web.app run --host 127.0.0.1 --port 5000 --debug

check: lint test
	@echo "All checks passed"
