# Spravoshnik EPB Frontend

GigaStudio UI integrated as the web client for the existing FastAPI modular monolith.

## Prerequisites

- Node.js 22+ (verified with Node.js 24)
- npm 11+
- FastAPI backend running at `http://127.0.0.1:8000` by default

## Install and run

```powershell
npm ci
npm run dev
```

Open `http://localhost:3000`. Production verification:

```powershell
npm test
npm run lint
npm run typecheck
npm run build
npm start
```

## Environment

Copy `.env.example` to `.env.local` when overriding defaults:

```env
BACKEND_ORIGIN=http://127.0.0.1:8000
NEXT_PUBLIC_API_BASE_URL=/backend
```

`BACKEND_ORIGIN` is server-only and must be an HTTP(S) origin without a path. Next.js proxies `/backend/*` to FastAPI so the browser remains same-origin and can use the existing HttpOnly session cookie. `NEXT_PUBLIC_API_BASE_URL` is the browser-visible API prefix; leave it as `/backend` unless the deployment deliberately provides another same-origin gateway.

## Authentication and architecture boundaries

- FastAPI owns login, server-side sessions, users, RBAC, permissions, scopes, audit, business rules, and persistence.
- Browser calls use `credentials: include`; tokens are not stored in JavaScript or local storage.
- PostgreSQL is the only source of truth. This frontend has no Prisma, database, or business Server Actions.
- `/organizations` uses real backend data. The dashboard, contracts, expertise, tasks, NPD, calendar, search, and notifications still contain explicit demo/mock data and are labelled in the UI.
