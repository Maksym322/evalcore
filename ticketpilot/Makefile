.PHONY: dev test lint migrate ingest

dev:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check .
	ruff format --check .
	mypy app

migrate:
	alembic upgrade head

ingest:
	@echo "ingestion arrives in M3.3"
