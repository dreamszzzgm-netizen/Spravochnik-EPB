# PR6 Tasks API Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mocked `/tasks` registry with a typed, API-backed task registry using the existing Tasks Core backend.

**Architecture:** Add a focused `frontend/src/lib/api/tasks.ts` transport module, then convert `/tasks` into a client page that consumes the real paginated endpoint. Keep backend authorization authoritative, preserve existing design components, and defer task mutation/detail/checklist UI to later PR6 checkpoints.

**Tech Stack:** Next.js 16.2.1, React 19.2, TypeScript 5.8, Vitest 3.2, existing `apiRequest`, shadcn/ui, lucide-react.

## Global Constraints

- Expertise development is paused; do not modify Expertise behavior.
- Do not add frontend dependencies.
- Do not implement fake client-only search against one page of server results.
- Keep task status values exactly `new | in_progress | completed | cancelled`.
- Keep task priority values exactly `low | normal | high | urgent`.
- Keep authorization on the backend; do not duplicate scope rules in the page.
- Use TDD: failing test first, then minimal production code.

---

## File Structure

| File | Action | Responsibility |
| --- | --- | --- |
| `frontend/src/lib/api/tasks.test.ts` | Create | Transport/query contract tests |
| `frontend/src/lib/api/tasks.ts` | Create | Typed Tasks API client and labels |
| `frontend/src/app/tasks/page.test.ts` | Create | Source-level regression ensuring `/tasks` uses real API and not mock-data |
| `frontend/src/app/tasks/page.tsx` | Modify | API-backed registry, filters, pagination and states |
| `PROJECT_STATUS.md` | Modify | Record the completed PR6 Tasks workspace checkpoint after verification |

### Task 1: Typed Tasks API client

**Files:**
- Create: `frontend/src/lib/api/tasks.test.ts`
- Create: `frontend/src/lib/api/tasks.ts`

**Interfaces:**
- Produces: `TaskStatus`, `TaskPriority`, `TaskResponse`, `TaskListResponse`, `TASK_STATUS_LABELS`, `TASK_PRIORITY_LABELS`, `getTasks()`.

- [ ] **Step 1: Write the failing transport tests**

Create `frontend/src/lib/api/tasks.test.ts` with tests that mock `fetch`, call `getTasks()`, and assert:

```ts
await getTasks({
  page: 2,
  page_size: 20,
  status: "in_progress",
  priority: "urgent",
  is_overdue: true,
});

expect(fetchMock).toHaveBeenCalledWith(
  "/backend/api/tasks?page=2&page_size=20&status=in_progress&priority=urgent&is_overdue=true",
  expect.objectContaining({ credentials: "include" }),
);
```

Also assert the Russian labels:

```ts
expect(TASK_STATUS_LABELS.completed).toBe("Выполнена");
expect(TASK_PRIORITY_LABELS.urgent).toBe("Срочный");
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run from `frontend/`:

```bash
npm test -- src/lib/api/tasks.test.ts
```

Expected: FAIL because `./tasks` does not exist.

- [ ] **Step 3: Implement the minimal typed client**

Create `frontend/src/lib/api/tasks.ts` with backend-exact unions and query serialization:

```ts
export type TaskStatus = "new" | "in_progress" | "completed" | "cancelled";
export type TaskPriority = "low" | "normal" | "high" | "urgent";

export interface TaskResponse {
  id: string;
  title: string;
  description: string | null;
  creator_employee_id: string;
  due_date: string | null;
  priority: TaskPriority;
  status: TaskStatus;
  is_personal: boolean;
  assignee_ids: string[];
  links: { kind: string; entity_id: string; is_primary: boolean }[];
  is_overdue: boolean;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
  deleted_at: string | null;
  version: number;
}
```

`getTasks()` serializes only supplied params and delegates to `apiRequest<TaskListResponse>()`.

- [ ] **Step 4: Re-run the focused test and confirm GREEN**

```bash
npm test -- src/lib/api/tasks.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api/tasks.ts frontend/src/lib/api/tasks.test.ts
git commit -m "feat(tasks): add typed frontend API client"
```

### Task 2: Replace mocked `/tasks` registry

**Files:**
- Create: `frontend/src/app/tasks/page.test.ts`
- Modify: `frontend/src/app/tasks/page.tsx`

**Interfaces:**
- Consumes: `getTasks`, `TaskResponse`, `TaskStatus`, `TaskPriority`, `TASK_STATUS_LABELS` from Task 1.
- Produces: real API-backed `/tasks` registry.

- [ ] **Step 1: Write the failing page regression test**

Create `frontend/src/app/tasks/page.test.ts` that reads `page.tsx` and asserts:

```ts
expect(source).toContain('from "@/lib/api/tasks"');
expect(source).toContain("getTasks(");
expect(source).not.toContain('from "@/lib/mock-data"');
expect(source).not.toContain("myTasks");
```

- [ ] **Step 2: Run the focused test and confirm RED**

```bash
npm test -- src/app/tasks/page.test.ts
```

Expected: FAIL because the page still imports and maps `myTasks`.

- [ ] **Step 3: Implement the API-backed page**

Convert `page.tsx` to `"use client"` and add state for:

```ts
const [items, setItems] = useState<TaskResponse[]>([]);
const [total, setTotal] = useState(0);
const [page, setPage] = useState(1);
const [status, setStatus] = useState<TaskStatus | "">("");
const [priority, setPriority] = useState<TaskPriority | "">("");
const [overdueOnly, setOverdueOnly] = useState(false);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
```

Use an `AbortController` in `useEffect`, call:

```ts
getTasks(
  {
    page,
    page_size: 20,
    status: status || undefined,
    priority: priority || undefined,
    is_overdue: overdueOnly || undefined,
  },
  { signal: controller.signal },
)
```

Render:

- disabled search input with explanatory placeholder;
- status select;
- priority select;
- overdue-only checkbox/button;
- normalized error alert;
- loader;
- empty state;
- real task rows;
- backend pagination.

Map API priority to existing `PriorityBadge` values without importing `mock-data`:

```ts
const PRIORITY_BADGE_VALUE = {
  low: "низкий",
  normal: "обычный",
  high: "высокий",
  urgent: "срочный",
} as const;
```

- [ ] **Step 4: Re-run the focused page test and confirm GREEN**

```bash
npm test -- src/app/tasks/page.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run frontend verification**

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/tasks/page.tsx frontend/src/app/tasks/page.test.ts
git commit -m "feat(tasks): use real backend task registry"
```

### Task 3: Record checkpoint and full verification

**Files:**
- Modify: `PROJECT_STATUS.md`

- [ ] **Step 1: Record the checkpoint**

Add a PR6 subsection stating that `/tasks` is API-backed, filters/pagination are real, search remains deferred until backend search exists, and Expertise remains paused.

- [ ] **Step 2: Run final frontend verification again on exact branch head**

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Expected: all PASS.

- [ ] **Step 3: Commit status evidence**

```bash
git add PROJECT_STATUS.md
git commit -m "docs: record PR6 tasks workspace checkpoint"
```

- [ ] **Step 4: Open a draft PR**

Base: `agent/integration-cp52-smart-import-hardening`  
Head: `agent/pr6-tasks-api-workspace`

PR title:

```text
PR6: migrate Tasks workspace to real API
```

PR body must include changed scope, verification results, and explicit note that Expertise behavior was not modified.
