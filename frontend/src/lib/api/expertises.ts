import { apiRequest } from "./client";

export type ExpertiseStatus =
  | "preparation"
  | "document_collection"
  | "inspection"
  | "conclusion_preparation"
  | "internal_approval"
  | "ready_for_registration"
  | "rtn_review"
  | "rtn_rework"
  | "registered"
  | "received_by_customer"
  | "completed";

export const EXPERTISE_STATUS_LABELS: Record<ExpertiseStatus, string> = {
  preparation: "Подготовка",
  document_collection: "Сбор документов",
  inspection: "Обследование",
  conclusion_preparation: "Подготовка заключения",
  internal_approval: "Внутреннее согласование",
  ready_for_registration: "Готово к регистрации",
  rtn_review: "На рассмотрении в РТН",
  rtn_rework: "Отказ РТН / Требует доработки",
  registered: "Зарегистрировано",
  received_by_customer: "Получено заказчиком",
  completed: "Завершено",
};

export interface ExpertiseSubject {
  technical_device_id: string | null;
  building_id: string | null;
}

export interface ExpertiseResponse {
  id: string;
  contract_id: string;
  expertise_type_id: string;
  status: ExpertiseStatus;
  internal_number: string | null;
  responsible_expert_id: string;
  comment: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  subject: ExpertiseSubject;
  contract_item_ids: string[];
  contract_number: string | null;
  organization_name: string | null;
  expertise_type_name: string | null;
  responsible_expert_name: string | null;
  subject_kind: string | null;
  subject_name: string | null;
}

export interface ExpertiseListResponse {
  items: ExpertiseResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface ExpertiseStatusHistoryResponse {
  id: string;
  from_status: ExpertiseStatus | null;
  to_status: ExpertiseStatus;
  changed_at: string;
  changed_by: string;
  reason: string | null;
}

export interface CreateExpertiseInput {
  contract_id: string;
  expertise_type_id: string;
  responsible_expert_id: string;
  contract_item_ids: string[];
  internal_number?: string;
  comment?: string;
  subject: ExpertiseSubject;
}

export function getExpertises(
  params: { page?: number; page_size?: number; status?: ExpertiseStatus; q?: string } = {},
  options: { signal?: AbortSignal } = {},
) {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.status) query.set("status", params.status);
  if (params.q) query.set("q", params.q);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest<ExpertiseListResponse>(`/api/expertises${suffix}`, options);
}

export function getExpertise(id: string, options: { signal?: AbortSignal } = {}) {
  return apiRequest<ExpertiseResponse>(`/api/expertises/${id}`, options);
}

export function createExpertise(input: CreateExpertiseInput) {
  return apiRequest<ExpertiseResponse>("/api/expertises", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function changeExpertiseStatus(
  id: string,
  input: { status: ExpertiseStatus; expected_version: number; reason?: string },
) {
  return apiRequest<ExpertiseResponse>(`/api/expertises/${id}/status`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getExpertiseStatusHistory(id: string, options: { signal?: AbortSignal } = {}) {
  return apiRequest<ExpertiseStatusHistoryResponse[]>(
    `/api/expertises/${id}/status-history`,
    options,
  );
}

export interface ContractOption {
  id: string;
  number: string;
  customer_organization_id: string;
}

export function listContracts(options: { signal?: AbortSignal } = {}) {
  return apiRequest<{ items: ContractOption[]; total: number }>("/api/contracts", options);
}

export interface ContractItemOption {
  id: string;
  name: string;
  technical_device_ids: string[];
  building_ids: string[];
}

export function listContractItems(contractId: string, options: { signal?: AbortSignal } = {}) {
  return apiRequest<ContractItemOption[]>(`/api/contracts/${contractId}/items`, options);
}

export interface ExpertiseTypeOption {
  id: string;
  code: string;
  name: string;
}

export function listExpertiseTypes(options: { signal?: AbortSignal } = {}) {
  return apiRequest<ExpertiseTypeOption[]>("/api/reference/expertise-types", options);
}

export interface DeviceOption {
  id: string;
  name: string;
}

export function listDevices(options: { signal?: AbortSignal } = {}) {
  return apiRequest<{ items: DeviceOption[] }>("/api/technical-devices", options);
}

export interface BuildingOption {
  id: string;
  name: string;
}

export function listBuildings(options: { signal?: AbortSignal } = {}) {
  return apiRequest<{ items: BuildingOption[] }>("/api/buildings", options);
}

export interface EmployeeOption {
  id: string;
  full_name: string;
  position: string | null;
  employment_type: string;
}

export function listEmployees(options: { signal?: AbortSignal } = {}) {
  return apiRequest<EmployeeOption[]>("/api/employees", options);
}

export type ExpertiseParticipantRole = "expert" | "specialist";

export const EXPERTISE_PARTICIPANT_ROLE_LABELS: Record<ExpertiseParticipantRole, string> = {
  expert: "Эксперт",
  specialist: "Специалист",
};

export interface ExpertiseParticipantResponse {
  id: string;
  expertise_id: string;
  employee_id: string;
  participation_role: ExpertiseParticipantRole;
  employee_name: string | null;
  position: string | null;
}

export function getExpertiseParticipants(
  id: string,
  options: { signal?: AbortSignal } = {},
) {
  return apiRequest<ExpertiseParticipantResponse[]>(`/api/expertises/${id}/participants`, options);
}

export function addExpertiseParticipant(
  id: string,
  input: { employee_id: string; participation_role: ExpertiseParticipantRole },
) {
  return apiRequest<ExpertiseParticipantResponse>(`/api/expertises/${id}/participants`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function removeExpertiseParticipant(id: string, employeeId: string) {
  return apiRequest<void>(`/api/expertises/${id}/participants/${employeeId}`, {
    method: "DELETE",
  });
}

export interface ExpertiseTaskSummary {
  id: string;
  title: string;
  status: string;
  priority: string;
  due_date: string | null;
  created_at: string;
}

export function getExpertiseTasks(id: string, options: { signal?: AbortSignal } = {}) {
  return apiRequest<ExpertiseTaskSummary[]>(`/api/expertises/${id}/tasks`, options);
}

export interface WorkflowOption {
  id: string;
  code: string;
  name: string;
}

export function listWorkflowTemplates(options: { signal?: AbortSignal } = {}) {
  return apiRequest<WorkflowOption[]>("/api/expertises/workflow-templates", options);
}

export interface WorkflowStartedTask {
  id: string;
  title: string;
  status: string;
  source_workflow_template_version_id: string | null;
  source_workflow_task_template_id: string | null;
}

export function startExpertiseWorkflow(id: string, workflowTemplateId: string) {
  return apiRequest<WorkflowStartedTask[]>(`/api/expertises/${id}/workflow/start`, {
    method: "POST",
    body: JSON.stringify({ workflow_template_id: workflowTemplateId }),
  });
}
