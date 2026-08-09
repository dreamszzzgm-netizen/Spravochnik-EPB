import { apiRequest } from "./client";
import type { CurrentUserResponse, HealthResponse, LoginResponse, OrganizationResponse } from "./types";

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
export const getOrganizations = (options: ResourceOptions = {}) => apiRequest<OrganizationResponse[]>("/api/organizations", options);
export const logout = () => apiRequest<void>("/api/auth/logout", { method: "POST" });
