import { apiRequest } from "./client";

export interface OrganizationDocumentResponse {
  id: string;
  organization_id: string;
  document_type: string;
  title: string;
  original_filename: string;
  content_type: string | null;
  sha256: string;
  size_bytes: number;
  issued_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrganizationDocumentListResponse {
  source_available: boolean;
  items: OrganizationDocumentResponse[];
}

export function getOrganizationDocuments(
  organizationId: string,
  options: { signal?: AbortSignal } = {},
) {
  return apiRequest<OrganizationDocumentListResponse>(
    `/api/organizations/${organizationId}/documents`,
    options,
  );
}

export function uploadOrganizationDocument(
  organizationId: string,
  input: {
    file: File;
    documentType: string;
    title: string;
    issuedAt?: string;
    expiresAt?: string;
  },
) {
  const form = new FormData();
  form.append("file", input.file);
  form.append("document_type", input.documentType);
  form.append("title", input.title);
  if (input.issuedAt) form.append("issued_at", input.issuedAt);
  if (input.expiresAt) form.append("expires_at", input.expiresAt);
  return apiRequest<OrganizationDocumentResponse>(
    `/api/organizations/${organizationId}/documents`,
    { method: "POST", body: form, timeoutMs: 60_000 },
  );
}

export function deleteOrganizationDocument(organizationId: string, documentId: string) {
  return apiRequest<void>(
    `/api/organizations/${organizationId}/documents/${documentId}`,
    { method: "DELETE" },
  );
}

export function organizationDocumentDownloadHref(
  organizationId: string,
  documentId: string,
) {
  return `/backend/api/organizations/${organizationId}/documents/${documentId}/download`;
}
