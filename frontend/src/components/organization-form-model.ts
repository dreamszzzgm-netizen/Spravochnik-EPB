import type { IdentifierType, OrganizationCreatePayload, OrganizationType } from "@/lib/api/types";

export interface OrganizationFormValues {
  legalName: string;
  shortName: string;
  orgType: OrganizationType;
  legalAddress: string;
  actualAddress: string;
  residenceAddress: string;
  directorName: string;
  passportDetails: string;
  phone: string;
  email: string;
  comment: string;
  identifiers: Partial<Record<IdentifierType, string>>;
}

export const EMPTY_ORGANIZATION_FORM: OrganizationFormValues = {
  legalName: "",
  shortName: "",
  orgType: "legal_entity",
  legalAddress: "",
  actualAddress: "",
  residenceAddress: "",
  directorName: "",
  passportDetails: "",
  phone: "",
  email: "",
  comment: "",
  identifiers: {},
};

export function identifierTypesFor(type: OrganizationType): IdentifierType[] {
  return type === "individual_entrepreneur" ? ["inn", "ogrnip"] : ["inn", "kpp", "ogrn"];
}

export function buildOrganizationPayload(values: OrganizationFormValues): OrganizationCreatePayload {
  const isIp = values.orgType === "individual_entrepreneur";
  const identifiers = identifierTypesFor(values.orgType)
    .filter((type) => values.identifiers[type]?.trim())
    .map((type) => ({
      identifier_type: type,
      identifier_value: values.identifiers[type]?.trim() ?? "",
      is_primary: type === "inn",
    }));
  return {
    legal_name: values.legalName.trim(),
    short_name: values.shortName.trim() || null,
    organization_type: values.orgType,
    legal_address: isIp ? null : values.legalAddress.trim() || null,
    actual_address: isIp ? null : values.actualAddress.trim() || null,
    residence_address: isIp ? values.residenceAddress.trim() || null : null,
    director_name: isIp ? null : values.directorName.trim() || null,
    passport_details: isIp ? values.passportDetails.trim() || null : null,
    phone: values.phone.trim() || null,
    email: values.email.trim() || null,
    comment: values.comment.trim() || null,
    identifiers,
  };
}
