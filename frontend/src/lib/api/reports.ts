import { apiRequest } from "./client";

export type DocumentControlStatus =
  | "expired"
  | "expiring_14"
  | "expiring_40"
  | "valid"
  | "missing"
  | "no_expiry";

export interface DocumentIssueResponse {
  organization_id: string;
  organization_name: string;
  document_type: string;
  document_title: string;
  status: DocumentControlStatus;
  expires_at: string | null;
  days_left: number | null;
}

export interface ManagementReportResponse {
  organizations_total: number;
  contracts: {
    total: number;
    active: number;
    completed: number;
    terminated: number;
  };
  tasks: {
    total: number;
    new: number;
    in_progress: number;
    completed: number;
    cancelled: number;
    overdue: number;
  };
  documents: {
    source_available: boolean;
    total: number;
    expired: number;
    expiring_14: number;
    expiring_40: number;
    missing: number;
    no_expiry: number;
    issues: DocumentIssueResponse[];
  };
  expertises: {
    source_available: boolean;
  };
}

export function getManagementReport(options: { signal?: AbortSignal } = {}) {
  return apiRequest<ManagementReportResponse>("/api/reports/management", options);
}
