import { apiRequest } from "./client";
import type {
  CurrentUserResponse,
  HealthResponse,
  LoginResponse,
  OrganizationCreatePayload,
  OrganizationIdentifierResponse,
  OrganizationPaginatedResponse,
  OrganizationResponse,
  OrganizationUpdatePayload,
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

export const getOrganization = (id: string, options: ResourceOptions = {}) =>
  apiRequest<OrganizationResponse>(`/api/organizations/${id}`, options);

export const updateOrganization = (id: string, payload: OrganizationUpdatePayload) =>
  apiRequest<OrganizationResponse>(`/api/organizations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const getOrganizationIdentifiers = (id: string, options: ResourceOptions = {}) =>
  apiRequest<OrganizationIdentifierResponse[]>(`/api/organizations/${id}/identifiers`, options);
