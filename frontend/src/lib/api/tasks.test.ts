import { afterEach, describe, expect, it, vi } from "vitest";

import {
  TASK_PRIORITY_LABELS,
  TASK_STATUS_LABELS,
  getTasks,
} from "./tasks";

describe("Tasks API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("serializes supported task registry filters using backend enum values", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], total: 0, page: 2, page_size: 20 }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    await getTasks({
      page: 2,
      page_size: 20,
      status: "in_progress",
      priority: "urgent",
      is_overdue: true,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/backend/api/tasks?page=2&page_size=20&status=in_progress&priority=urgent&is_overdue=true",
      expect.objectContaining({
        credentials: "include",
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("omits undefined filters instead of sending empty query values", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], total: 0, page: 1, page_size: 20 }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    await getTasks({ page: 1, page_size: 20 });

    expect(fetchMock).toHaveBeenCalledWith(
      "/backend/api/tasks?page=1&page_size=20",
      expect.any(Object),
    );
  });

  it("keeps Russian presentation labels separate from backend transport values", () => {
    expect(TASK_STATUS_LABELS.new).toBe("Новая");
    expect(TASK_STATUS_LABELS.in_progress).toBe("В работе");
    expect(TASK_STATUS_LABELS.completed).toBe("Выполнена");
    expect(TASK_STATUS_LABELS.cancelled).toBe("Отменена");

    expect(TASK_PRIORITY_LABELS.low).toBe("Низкий");
    expect(TASK_PRIORITY_LABELS.normal).toBe("Обычный");
    expect(TASK_PRIORITY_LABELS.high).toBe("Высокий");
    expect(TASK_PRIORITY_LABELS.urgent).toBe("Срочный");
  });
});
