"use client";

import { useCallback, useState } from "react";

import {
  EMPTY_ORGANIZATION_FORM,
  type OrganizationFormValues,
} from "@/components/organization-form-model";
import type { IdentifierType, OrganizationImportPreviewResponse, OrganizationType } from "@/lib/api/types";

export function useOrganizationForm() {
  const [values, setValues] = useState<OrganizationFormValues>(EMPTY_ORGANIZATION_FORM);

  const setText = useCallback((
    field: Exclude<keyof OrganizationFormValues, "orgType" | "identifiers">,
    value: string,
  ) => setValues((previous) => ({ ...previous, [field]: value })), []);

  const setType = useCallback(
    (orgType: OrganizationType) => setValues((previous) => ({ ...previous, orgType })),
    [],
  );

  const setIdentifier = useCallback((type: IdentifierType, value: string) => {
    setValues((previous) => ({
      ...previous,
      identifiers: { ...previous.identifiers, [type]: value },
    }));
  }, []);

  const applyImport = useCallback((preview: OrganizationImportPreviewResponse) => {
    const candidate = preview.candidate;
    setValues((previous) => {
      const identifiers = { ...previous.identifiers };
      for (const identifier of candidate.identifiers) {
        identifiers[identifier.identifier_type] = identifier.identifier_value;
      }
      return {
        ...previous,
        orgType: candidate.organization_type,
        legalName: candidate.legal_name ?? previous.legalName,
        shortName: candidate.short_name ?? "",
        legalAddress: candidate.legal_address ?? "",
        actualAddress: candidate.actual_address ?? "",
        residenceAddress: candidate.residence_address ?? "",
        directorName: candidate.director_name ?? "",
        passportDetails: candidate.passport_details ?? "",
        phone: candidate.phone ?? "",
        email: candidate.email ?? "",
        identifiers,
      };
    });
  }, []);

  return { values, setValues, setText, setType, setIdentifier, applyImport };
}
