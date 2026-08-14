import { apiRequest } from "./client";

export type TaskStatus = "new" | "in_progress" | "completed" | "cancelled";
export type TaskPriority = "low" | "normal" | "high" | "urgent";
export type TaskLinkKind =
  | "organization"
  | "contract"
  | "contract_item"
  | "technical_device"
  | "building"
  | "opo";

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  new: "Новая",
  in_progress: "В работе",
  completed: "Выполнена",
  cancelled: "Отменена",
};

export const TASK_PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Низкий",
  normal: "Обычный",
  high: "Высокий",
  urgent: "Срочный",
};

export interface TaskLinkResponse {
  kind: TaskLinkKind;
  entity_id: string;
  is_primary: boolean;
}

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
  links: TaskLinkResponse[];
  is_overdue: boolean;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
  deleted_at: string | null;
  version: number;
}

export interface TaskListResponse {
  items: TaskResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface TaskListParams {
  page?: number;
  page_size?: number;
  status?: TaskStatus;
  priority?: TaskPriority;
  is_overdue?: boolean;
}

export function getTasks(
  params: TaskListParams = {},
  options: { signal?: AbortSignal } = {},
) {
  const query = new URLSearchParams();
  if (params.page !== undefined) query.set("page", String(params.page));
  if (params.page_size !== undefined) query.set("page_size", String(params.page_size));
  if (params.status !== undefined) query.set("status", params.status);
  if (params.priority !== undefined) query.set("priority", params.priority);
  if (params.is_overdue !== undefined) query.set("is_overdue", String(params.is_overdue));

  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest<TaskListResponse>(`/api/tasks${suffix}`, options);
}
