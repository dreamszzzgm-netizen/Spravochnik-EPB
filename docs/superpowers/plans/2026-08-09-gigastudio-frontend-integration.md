# GigaStudio Frontend Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import GigaStudio as the repository frontend and establish a tested, session-safe connection to the existing FastAPI API without duplicating backend responsibilities.

**Architecture:** Preserve the GigaStudio presentation layer under `frontend/`. Browser requests use a same-origin `/backend/*` Next.js rewrite to the environment-configured FastAPI origin, while a single typed client handles JSON, cookies, timeout, and normalized HTTP failures. Health, current-user, and organization-list data become real; every remaining mock-backed surface is visibly labelled demo.

**Tech Stack:** Next.js 16.2.1, React 19.2, TypeScript 5.8, Tailwind 3.4, npm, Vitest, FastAPI, server-side cookie sessions.

## Global Constraints

- FastAPI remains the only business-logic and authorization backend.
- PostgreSQL remains the only source of truth.
- No Prisma, second database, Next Server Action business layer, duplicate auth, or duplicate RBAC.
- Existing backend migrations and tests must remain unchanged.
- `NEXT_PUBLIC_API_BASE_URL` defaults to `/backend`; `BACKEND_ORIGIN` configures the proxy destination.
- All browser API requests use `credentials: "include"` and an explicit timeout.
- Stage 2 business features are out of scope.

---

### Task 1: Import and normalize GigaStudio

**Files:** Create `frontend/**` from the archive; modify `frontend/package.json`, `frontend/next.config.mjs`, `frontend/.npmrc`, `frontend/README.md`.

**Interfaces:** Produces a strict, npm-based Next.js build with `lint`, `typecheck`, and `test` scripts.

- [ ] Copy the archive root contents into `frontend/` without nesting its outer directory.
- [ ] Retain `package-lock.json`, remove `bun.lock`, unsafe npm flags, `typescript.ignoreBuildErrors`, and the absolute Turbopack root.
- [ ] Add working ESLint, TypeScript, and Vitest scripts and install dependencies with `npm ci`.
- [ ] Run lint/typecheck/build and resolve root causes of failures.

### Task 2: Build the tested API foundation

**Files:** Create `frontend/src/lib/api/{client,errors,types,config}.ts` and colocated tests; modify `frontend/next.config.mjs`.

**Interfaces:** Produces `apiRequest<T>(path, options)`, `ApiError`, `getHealth()`, `getCurrentUser()`, and `getOrganizations()`.

- [ ] Write tests that fail for URL composition, cookie credentials, JSON handling, timeout, and 401/403/404/422/500 normalization.
- [ ] Implement only enough API code to pass each test.
- [ ] Add the `/backend/:path*` rewrite to `${BACKEND_ORIGIN}/:path*` with a validated HTTP(S) origin.
- [ ] Run the focused tests, then the complete frontend test suite.

### Task 3: Connect real shell data and isolate demos

**Files:** Modify shell/user-menu/top-bar/organizations and demo-backed pages; create focused API/state components as needed.

**Interfaces:** Consumes current-user DTO `{id, employee_id, username, is_superuser, must_change_password}` and organization DTO `{id, legal_name, short_name, organization_type, ...}` exactly as returned by FastAPI.

- [ ] Add failing component/adapter tests for health state, current-user display, organization DTO mapping, and error states.
- [ ] Replace the static online label with real `/health/live` state.
- [ ] Replace the static user identity and logout with `/api/auth/me` and `/api/auth/logout`; do not invent roles or permissions.
- [ ] Use the real `/api/organizations` list with explicit unauthenticated, forbidden, loading, empty, and unavailable states.
- [ ] Add an unmistakable demo-data badge to all remaining mock-backed pages and components.

### Task 4: Document contracts and verify both applications

**Files:** Create `docs/FRONTEND_INTEGRATION_AUDIT.md`, `docs/FRONTEND_API_MAP.md`; update `frontend/README.md`.

**Interfaces:** Documents actual endpoints, missing contracts, environment, auth assumptions, and mock status.

- [ ] Record the backend/frontend audit and feature-to-endpoint map with severity-ranked gaps.
- [ ] Run backend ruff, format check, pytest, migration-head/import/startup checks.
- [ ] Run frontend test, lint, typecheck, build, and browser smoke checks for all primary routes.
- [ ] Inspect `git diff`, preserve unrelated untracked files, and request independent code review.
