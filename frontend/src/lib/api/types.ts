export interface HealthResponse {
  status: string;
  database?: string | null;
  storage?: string | null;
  version?: string;
}

export interface CurrentUserResponse {
  id: string;
  employee_id: string;
  username: string;
  is_superuser: boolean;
  must_change_password: boolean;
  permissions: string[];
}

export interface LoginResponse {
  must_change_password: boolean;
}

export type OrganizationType = "legal_entity" | "individual_entrepreneur" | "branch";

export interface OrganizationResponse {
  id: string;
  organization_type: OrganizationType;
  legal_name: string;
  short_name: string | null;
  parent_id: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}
