.PHONY: dev test lint

dev:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .
	ruff format --check .
	mypy evalcore
