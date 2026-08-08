# Spravoshnik EPB — Stage 0 Foundation

Технический фундамент Spravoshnik EPB v1.2.

## Stack

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL 17
- Pydantic Settings
- pytest
- persistent DB-backed jobs/outbox
- local file storage abstraction with mandatory SHA-256

## Scope Stage 0

Реализовано только то, что разрешено `DEVELOPMENT_PLAN.md` для Этапа 0:

- application bootstrap;
- typed configuration;
- structured logging context with request/correlation IDs;
- SQLAlchemy engine/session;
- Alembic migrations;
- `stored_files`;
- `background_jobs`;
- `outbox_events`;
- local storage abstraction;
- worker and scheduler as separate processes;
- health endpoint;
- unit/integration test foundation;
- CI with PostgreSQL.

Бизнес-модули намеренно не реализованы.

## Local start

```bash
cp .env.example .env
python -m pip install -e ".[dev]"
docker compose up -d postgres postgres-test
alembic upgrade head
uvicorn app.main:app --reload
```

Health:

```text
GET /health
GET /health/live
GET /health/ready
```

## Tests

```bash
pytest
```

Для integration tests требуется PostgreSQL:

```bash
TEST_DATABASE_URL=postgresql+psycopg://spravoshnik:spravoshnik@localhost:5433/spravoshnik_test pytest -m integration
```

## Processes

API:

```bash
spravoshnik-api
```

Worker:

```bash
spravoshnik-worker
```

Scheduler:

```bash
spravoshnik-scheduler
```

На Этапе 0 scheduler не создаёт бизнес-задачи: он предоставляет отдельный процесс и инфраструктурную точку расширения для следующих этапов.
