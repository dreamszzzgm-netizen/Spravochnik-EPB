import { apiRequest } from "./client";
import type {
  BuildingCreatePayload,
  BuildingPaginatedResponse,
  BuildingResponse,
  CurrentUserResponse,
  HealthResponse,
  ImportCandidateResponse,
  ImportReportResponse,
  ImportSessionListResponse,
  ImportSessionResponse,
  LoginResponse,
  OPOCreatePayload,
  OPOPaginatedResponse,
  OPOResponse,
  OrganizationCompletenessResponse,
  OrganizationContactCreatePayload,
  OrganizationContactResponse,
  OrganizationCreatePayload,
  OrganizationIdentifierResponse,
  OrganizationImportPreviewResponse,
  OrganizationPaginatedResponse,
  OrganizationParentSearchResult,
  OrganizationResponse,
  OrganizationUpdatePayload,
  ReferenceItemResponse,
  TechnicalDeviceCreatePayload,
  TechnicalDevicePaginatedResponse,
  TechnicalDeviceResponse,
} from "./types";

type ResourceOptions = { signal?: AbortSignal };

export const getHealth = (options: ResourceOptions = {}) => apiRequest<HealthResponse>("/health/live", options);
export const getCurrentUser = (options: ResourceOptions = {}) => apiRequest<CurrentUserResponse>("/api/auth/me", options);
export const login = (username: string, password: string) =>
  apiRequest<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
export const changePassword = (currentPassword: string, newPassword: string) =>
  apiRequest<void>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
export const getOrganizations = (params: { q?: string; page?: number; page_size?: number; signal?: AbortSignal } = {}) => {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set("q", params.q);
  if (params.page != null) searchParams.set("page", String(params.page));
  if (params.page_size != null) searchParams.set("page_size", String(params.page_size));
  const qs = searchParams.toString();
  return apiRequest<OrganizationPaginatedResponse>(`/api/organizations${qs ? `?${qs}` : ""}`, { signal: params.signal });
};
export const logout = () => apiRequest<void>("/api/auth/logout", { method: "POST" });

export const createOrganization = (payload: OrganizationCreatePayload) =>
  apiRequest<OrganizationResponse>("/api/organizations", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const previewOrganizationImport = (text: string) =>
  apiRequest<OrganizationImportPreviewResponse>("/api/organizations/import-preview", {
    method: "POST",
    body: JSON.stringify({ text }),
  });

export const previewOrganizationImportFile = (file: File, options: ResourceOptions = {}) => {
  const form = new FormData();
  form.append("file", file);
  return apiRequest<OrganizationImportPreviewResponse>("/api/organizations/import-file-preview", {
    method: "POST",
    body: form,
    signal: options.signal,
  });
};

export const getOrganization = (id: string, options: ResourceOptions = {}) =>
  apiRequest<OrganizationResponse>(`/api/organizations/${id}`, options);

export const updateOrganization = (id: string, payload: OrganizationUpdatePayload) =>
  apiRequest<OrganizationResponse>(`/api/organizations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const getOrganizationIdentifiers = (id: string, options: ResourceOptions = {}) =>
  apiRequest<OrganizationIdentifierResponse[]>(`/api/organizations/${id}/identifiers`, options);

export const getOrganizationContacts = (id: string, options: ResourceOptions = {}) =>
  apiRequest<OrganizationContactResponse[]>(`/api/organizations/${id}/contacts`, options);

export const createOrganizationContact = (organizationId: string, payload: OrganizationContactCreatePayload) =>
  apiRequest<OrganizationContactResponse>(`/api/organizations/${organizationId}/contacts`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const deleteOrganizationContact = (organizationId: string, contactId: string) =>
  apiRequest<void>(`/api/organizations/${organizationId}/contacts/${contactId}`, { method: "DELETE" });

export const getOpoList = (
  params: {
    organization_id: string;
    q?: string;
    page?: number;
    page_size?: number;
    signal?: AbortSignal;
  },
) => {
  const searchParams = new URLSearchParams();
  searchParams.set("organization_id", params.organization_id);
  if (params.q) searchParams.set("q", params.q);
  if (params.page != null) searchParams.set("page", String(params.page));
  if (params.page_size != null) searchParams.set("page_size", String(params.page_size));
  return apiRequest<OPOPaginatedResponse>(`/api/opo?${searchParams.toString()}`, {
    signal: params.signal,
  });
};

export const getTechnicalDevices = (
  params: {
    organization_id: string;
    q?: string;
    page?: number;
    page_size?: number;
    signal?: AbortSignal;
  },
) => {
  const searchParams = new URLSearchParams();
  searchParams.set("organization_id", params.organization_id);
  if (params.q) searchParams.set("q", params.q);
  if (params.page != null) searchParams.set("page", String(params.page));
  if (params.page_size != null) searchParams.set("page_size", String(params.page_size));
  return apiRequest<TechnicalDevicePaginatedResponse>(
    `/api/technical-devices?${searchParams.toString()}`,
    { signal: params.signal },
  );
};

export const getBuildings = (
  params: {
    organization_id: string;
    q?: string;
    page?: number;
    page_size?: number;
    signal?: AbortSignal;
  },
) => {
  const searchParams = new URLSearchParams();
  searchParams.set("organization_id", params.organization_id);
  if (params.q) searchParams.set("q", params.q);
  if (params.page != null) searchParams.set("page", String(params.page));
  if (params.page_size != null) searchParams.set("page_size", String(params.page_size));
  return apiRequest<BuildingPaginatedResponse>(`/api/buildings?${searchParams.toString()}`, {
    signal: params.signal,
  });
};

export const createOpo = (payload: OPOCreatePayload) =>
  apiRequest<OPOResponse>("/api/opo", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const createTechnicalDevice = (payload: TechnicalDeviceCreatePayload) =>
  apiRequest<TechnicalDeviceResponse>("/api/technical-devices", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const createBuilding = (payload: BuildingCreatePayload) =>
  apiRequest<BuildingResponse>("/api/buildings", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const getHazardSigns = (options: ResourceOptions = {}) =>
  apiRequest<ReferenceItemResponse[]>("/api/reference/hazard-signs", options);

export const getActivityTypes = (options: ResourceOptions = {}) =>
  apiRequest<ReferenceItemResponse[]>("/api/reference/activity-types", options);

export const getOrganizationCompleteness = (id: string, options: ResourceOptions = {}) =>
  apiRequest<OrganizationCompletenessResponse>(`/api/organizations/${id}/completeness`, options);

export const searchOrganizationsForParent = (params: { q?: string; page?: number; page_size?: number; signal?: AbortSignal } = {}) => {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set("q", params.q);
  if (params.page != null) searchParams.set("page", String(params.page));
  if (params.page_size != null) searchParams.set("page_size", String(params.page_size));
  const qs = searchParams.toString();
  return apiRequest<OrganizationParentSearchResult[]>(`/api/organizations/search${qs ? `?${qs}` : ""}`, { signal: params.signal });
};

export const createImportSession = (options: ResourceOptions = {}) =>
  apiRequest<ImportSessionResponse>("/api/import/sessions", { method: "POST", ...options });

export const uploadImportExcel = (sessionId: string, file: File, options: ResourceOptions = {}) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<ImportSessionResponse>(`/api/import/sessions/${sessionId}/upload-excel`, {
    method: "POST",
    body: formData,
    ...options,
  });
};

export const getImportSessions = (options: ResourceOptions = {}) =>
  apiRequest<ImportSessionListResponse>("/api/import/sessions", options);

export const getImportSession = (sessionId: string, options: ResourceOptions = {}) =>
  apiRequest<ImportSessionResponse>(`/api/import/sessions/${sessionId}`, options);

export const getImportCandidates = (sessionId: string, options: ResourceOptions = {}) =>
  apiRequest<ImportCandidateResponse[]>(`/api/import/sessions/${sessionId}/candidates`, options);

export const updateImportCandidate = (
  sessionId: string,
  candidateId: string,
  payload: { proposed_action: string; normalized_data?: Record<string, unknown> },
  options: ResourceOptions = {},
) =>
  apiRequest<ImportCandidateResponse>(`/api/import/sessions/${sessionId}/candidates/${candidateId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    ...options,
  });

export const confirmImportSession = (sessionId: string, options: ResourceOptions = {}) =>
  apiRequest<ImportSessionResponse>(`/api/import/sessions/${sessionId}/confirm`, {
    method: "POST",
    ...options,
  });

export const getImportReport = (sessionId: string, options: ResourceOptions = {}) =>
  apiRequest<ImportReportResponse>(`/api/import/sessions/${sessionId}/report`, options);

export const cancelImportSession = (sessionId: string, options: ResourceOptions = {}) =>
  apiRequest<ImportSessionResponse>(`/api/import/sessions/${sessionId}/cancel`, {
    method: "POST",
    ...options,
  });