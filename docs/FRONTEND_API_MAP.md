# Frontend API Map

| Frontend feature | Required backend contract | Status | Stage 1 adaptation |
|---|---|---|---|
| Backend status | `GET /health/live` | Exists | Real status indicator through typed API client |
| Login | `POST /api/auth/login` | Exists | Client foundation supports cookie credentials; dedicated login screen is later scope |
| Current user | `GET /api/auth/me` | Partial | Real username/superuser only; no fabricated profile fields |
| Logout | `POST /api/auth/logout` | Exists | Real logout; expired session is treated as locally logged out |
| Organizations list | `GET /api/organizations` | Exists | Real list; 401/403/loading/empty/unavailable states |
| Organization identifiers | `GET /api/organizations/{id}/identifiers` | Exists | Deferred to detail workspace; avoids Stage 1 N+1 requests |
| Organization detail | Organization, contacts, identifiers endpoints | Backend exists, UI route missing | Stage 2 |
| Organization search/pagination | Queryable list projection | Missing | Small-list client name filter only |
| Contracts | Contract APIs | Missing | Explicit demo data |
| Expertise | Expertise APIs | Missing | Explicit demo data; dynamic route remains a visual template |
| Tasks | Task APIs | Missing | Explicit demo data |
| NPD | NPD APIs | Missing | Explicit demo data |
| Calendar | Calendar/deadline APIs | Missing | Explicit demo/empty state |
| Global search | Search read model | Missing | Existing command UI remains demo |
| Notifications | Notification APIs | Missing | Existing popover remains demo |

## Error contract

The frontend normalizes all non-2xx responses into `ApiError(status, detail, body)`. UI handling distinguishes 401 (authentication required), 403 (permission denied), 404, 422, and server failures. Requests time out with `ApiTimeoutError`; no backend error is converted into mock production data.
