.PHONY: install dev-up dev-down migrate test test-unit test-integration lint run worker scheduler

install:
	python -m pip install -e ".[dev]"

dev-up:
	docker compose up -d postgres postgres-test

dev-down:
	docker compose down

migrate:
	alembic upgrade head

test:
	pytest

test-unit:
	pytest tests/unit

test-integration:
	pytest -m integration tests/integration

lint:
	ruff check app tests

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	python -m app.jobs.worker

scheduler:
	python -m app.jobs.scheduler
