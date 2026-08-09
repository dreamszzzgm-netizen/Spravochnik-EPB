export function organizationName(organization: {
  short_name: string | null;
  legal_name: string;
}): string {
  return organization.short_name || organization.legal_name;
}

export function userInitials(username: string): string {
  const parts = username.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  if (parts.length > 1) return parts.slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  return username.slice(0, 2).toUpperCase();
}
