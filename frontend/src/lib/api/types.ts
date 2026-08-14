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
export type IdentifierType = "inn" | "kpp" | "ogrn" | "ogrnip" | "external_id";
export type ContactType = "director" | "chief_engineer" | "pb_specialist" | "accountant" | "other";

export interface OrganizationIdentifierCreate {
  identifier_type: IdentifierType;
  identifier_value: string;
  is_primary: boolean;
}

export interface OrganizationIdentifierResponse {
  id: string;
  organization_id: string;
  identifier_type: IdentifierType;
  identifier_value: string;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
}

export interface OrganizationContactResponse {
  id: string;
  organization_id: string;
  contact_type: ContactType;
  full_name: string;
  position: string | null;
  phone: string | null;
  email: string | null;
  is_primary: boolean;
}

export interface OrganizationContactCreatePayload {
  contact_type: ContactType;
  full_name: string;
  position: string | null;
  phone: string | null;
  email: string | null;
  is_primary: boolean;
}

export interface OrganizationCreatePayload {
  legal_name: string;
  short_name: string | null;
  organization_type: OrganizationType;
  legal_address: string | null;
  actual_address: string | null;
  residence_address: string | null;
  director_name: string | null;
  passport_details: string | null;
  phone: string | null;
  email: string | null;
  comment: string | null;
  bank_details: string | null;
  parent_id: string | null;
  identifiers: OrganizationIdentifierCreate[];
}

export interface OrganizationUpdatePayload {
  legal_name?: string | null;
  short_name?: string | null;
  organization_type?: OrganizationType | null;
  legal_address?: string | null;
  actual_address?: string | null;
  residence_address?: string | null;
  director_name?: string | null;
  passport_details?: string | null;
  phone?: string | null;
  email?: string | null;
  comment?: string | null;
  bank_details?: string | null;
  parent_id?: string | null;
  identifiers?: OrganizationIdentifierCreate[] | null;
}

export interface OrganizationResponse {
  id: string;
  organization_type: OrganizationType;
  legal_name: string;
  short_name: string | null;
  legal_address: string | null;
  actual_address: string | null;
  residence_address: string | null;
  director_name: string | null;
  passport_details: string | null;
  phone: string | null;
  email: string | null;
  comment: string | null;
  bank_details: string | null;
  parent_id: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrganizationPaginatedResponse {
  items: OrganizationResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface OrganizationImportCandidate {
  organization_type: OrganizationType;
  legal_name: string | null;
  short_name: string | null;
  legal_address: string | null;
  actual_address: string | null;
  residence_address: string | null;
  director_name: string | null;
  passport_details: string | null;
  phone: string | null;
  email: string | null;
  identifiers: OrganizationIdentifierCreate[];
}

export interface OrganizationImportPreviewResponse {
  candidate: OrganizationImportCandidate;
  warnings: string[];
  duplicate_warnings: string[];
}

export interface OPOResponse {
  id: string;
  name: string;
  registration_number: string;
  hazard_class: string;
  address: string;
  registration_date: string;
  owner_organization_id: string;
  operating_organization_id: string;
  deleted_at: string | null;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface OPOPaginatedResponse {
  items: OPOResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface TechnicalDeviceResponse {
  id: string;
  name: string;
  device_type: string;
  serial_number: string | null;
  opo_id: string | null;
  organization_id: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TechnicalDevicePaginatedResponse {
  items: TechnicalDeviceResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface BuildingResponse {
  id: string;
  name: string;
  building_type: string;
  opo_id: string | null;
  organization_id: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BuildingPaginatedResponse {
  items: BuildingResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReferenceItemResponse {
  id: string;
  code: string;
  name: string;
}

export type HazardClass =
  | "hazard_class_1"
  | "hazard_class_2"
  | "hazard_class_3"
  | "hazard_class_4";

export type TechnicalDeviceType =
  | "pressure_vessel"
  | "pipeline"
  | "lifting_mechanism"
  | "other";

export type BuildingType =
  | "industrial"
  | "warehouse"
  | "administrative"
  | "other";

export interface OPOCreatePayload {
  name: string;
  registration_number: string;
  hazard_class: HazardClass;
  address: string;
  registration_date: string;
  owner_organization_id: string;
  operating_organization_id: string;
  hazard_sign_ids: string[];
  activity_type_ids: string[];
  comment: string | null;
}

export interface TechnicalDeviceCreatePayload {
  name: string;
  device_type: TechnicalDeviceType;
  serial_number: string | null;
  opo_id: string | null;
  organization_id: string;
}

export interface BuildingCreatePayload {
  name: string;
  building_type: BuildingType;
  opo_id: string | null;
  organization_id: string;
}

export interface OrganizationCompletenessField {
  code: string;
  label: string;
  filled: boolean;
}

export interface OrganizationCompletenessResponse {
  status: "complete" | "needs_attention" | "missing_required";
  missing_required_fields: OrganizationCompletenessField[];
  warning_fields: OrganizationCompletenessField[];
}

export interface OrganizationParentSearchResult {
  id: string;
  legal_name: string;
  short_name: string | null;
  organization_type: string;
}
