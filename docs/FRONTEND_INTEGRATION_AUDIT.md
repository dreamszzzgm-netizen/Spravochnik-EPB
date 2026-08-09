# Frontend Integration Audit

## Baseline

- Backend: FastAPI modular monolith in `app/`, SQLAlchemy 2, Alembic migrations `0001` through `0004`, PostgreSQL, server-side sessions, RBAC, audit, jobs/outbox, and local file storage.
- Entry point: `app.main:app`; development port: `8000`.
- GigaStudio: Next.js 16.2.1, React 19.2, TypeScript, Tailwind, shadcn/ui, App Router, AppShell, and nine primary routes.
- Existing user work (`.superpowers/`, `HANDOFF.md`, `run.bat`) was left untouched.

## Decisions

1. GigaStudio was copied into `frontend/` without restructuring its presentation layer.
2. npm is the only package manager. The archive's Bun lock and registry-bound npm lock were replaced with a reproducible public-registry lock.
3. TypeScript build suppression, the absolute Turbopack root, wildcard framing, unsafe npm SSL settings, and the obsolete `next lint` script were removed.
4. The browser uses a same-origin `/backend/*` Next rewrite to `BACKEND_ORIGIN`. This avoids wildcard credentialed CORS and preserves FastAPI's HttpOnly cookie session.
5. A single typed API client provides configurable base URL, JSON parsing, `credentials: include`, 10-second default timeout, and normalized `ApiError` status/detail.
6. `/health/live`, `/api/auth/me`, `/api/auth/logout`, and `/api/organizations` are the first real connections.
7. Backend DTO names are adapted in frontend view models; backend domain contracts were not renamed for UI convenience.

## Mock isolation

Real now:

- backend reachability indicator;
- current session username and superuser flag;
- logout;
- organization list and client-side name filter.

Still demo/mock and explicitly labelled:

- dashboard KPIs/charts/activity;
- contracts;
- expertise list/detail;
- tasks;
- NPD;
- calendar content;
- command-search index;
- notifications.

## Findings

- **HIGH:** `/api/auth/me` lacks employee display name, email, effective roles, permissions, and scopes. The frontend shows only truthful fields and does not invent a role.
- **HIGH:** Direct cross-origin credential requests are not supported because backend CORS is absent. The same-origin proxy is the Stage 1 solution.
- **MEDIUM:** Organization list has no pagination/search and does not include primary identifiers or aggregate counts.
- **MEDIUM:** Resource-specific RBAC scope filtering is not applied by organization routes; backend work is required before exposing scoped organization access broadly.
- **LOW:** Several demo navigation links target routes not yet implemented; Next.js `not-found` handles them until later stages.
