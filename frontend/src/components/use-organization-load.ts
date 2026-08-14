"use client";

import { useEffect, useState } from "react";

import type { OrganizationFormValues } from "@/components/organization-form-model";
import { ApiError } from "@/lib/api/errors";
import { getOrganization, getOrganizationIdentifiers } from "@/lib/api/resources";
import type { IdentifierType } from "@/lib/api/types";

type SetValues = (values: OrganizationFormValues) => void;

export function useOrganizationLoad(organizationId: string | undefined, setValues: SetValues) {
  const [loading, setLoading] = useState(Boolean(organizationId));
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!organizationId) return;
    Promise.all([getOrganization(organizationId), getOrganizationIdentifiers(organizationId)])
      .then(([organization, identifiers]) => {
        const map: Partial<Record<IdentifierType, string>> = {};
        for (const identifier of identifiers) map[identifier.identifier_type] = identifier.identifier_value;
        setValues({
          legalName: organization.legal_name,
          shortName: organization.short_name ?? "",
          orgType: organization.organization_type,
          parentId: organization.parent_id ?? "",
          legalAddress: organization.legal_address ?? "",
          actualAddress: organization.actual_address ?? "",
          residenceAddress: organization.residence_address ?? "",
          directorName: organization.director_name ?? "",
          passportDetails: organization.passport_details ?? "",
          phone: organization.phone ?? "",
          email: organization.email ?? "",
          comment: organization.comment ?? "",
          bankDetails: organization.bank_details ?? "",
          identifiers: map,
        });
      })
      .catch((caught) => {
        setLoadError(caught instanceof ApiError ? caught.detail : "Ошибка загрузки организации");
      })
      .finally(() => setLoading(false));
  }, [organizationId, setValues]);

  return { loading, loadError };
}
