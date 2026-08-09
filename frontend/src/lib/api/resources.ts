import { apiRequest } from "./client";
import type { CurrentUserResponse, HealthResponse, OrganizationResponse } from "./types";

type ResourceOptions = { signal?: AbortSignal };

export const getHealth = (options: ResourceOptions = {}) => apiRequest<HealthResponse>("/health/live", options);
export const getCurrentUser = (options: ResourceOptions = {}) => apiRequest<CurrentUserResponse>("/api/auth/me", options);
export const getOrganizations = (options: ResourceOptions = {}) => apiRequest<OrganizationResponse[]>("/api/organizations", options);
export const logout = () => apiRequest<void>("/api/auth/logout", { method: "POST" });
