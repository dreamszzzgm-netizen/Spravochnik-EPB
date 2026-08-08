# Stage 1 Acceptance — Identity, Employees, Permissions

## Scope completed
- employees;
- employee business/function roles separated from authorization roles;
- users with Argon2 password hashes;
- role/permission catalog and user role assignments;
- scopes `ALL / ASSIGNED / RELATED / OWN`;
- server-side sessions with token hashes only;
- login/logout;
- absolute and inactivity timeouts;
- failed-login lock;
- session revocation;
- administrative reset + must-change-password flow;
- superuser authorization bypass;
- backend permission dependencies;
- authentication/business audit;
- initial superuser bootstrap command.

## Acceptance commands

```bash
docker compose up -d postgres
python -m pip install -e ".[dev]"
alembic upgrade head
pytest
ruff check app tests
```

Initial administrator:

```bash
spravoshnik-bootstrap-superuser \
  --username admin \
  --name "Administrator"
```

## Security decisions
- password: Argon2id (`argon2-cffi`);
- minimum password length enforced by application: 12;
- raw session tokens never stored in PostgreSQL;
- session cookies are HttpOnly + SameSite=Strict;
- `SESSION_COOKIE_SECURE=true` is required for HTTPS deployments;
- reset passwords/session tokens are not written to audit metadata;
- employee business functions do not grant authorization permissions.

## PostgreSQL-required checks
The integration suite validates migration, login lock, session timeout/revoke,
permission+scope and password-reset behavior against PostgreSQL.
