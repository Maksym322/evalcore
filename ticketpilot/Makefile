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
	python -m app.ingestion.cli $(SOURCE)
