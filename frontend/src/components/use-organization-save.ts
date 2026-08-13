"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

import { buildOrganizationPayload, type OrganizationFormValues } from "@/components/organization-form-model";
import { ApiError } from "@/lib/api/errors";
import { createOrganization, updateOrganization } from "@/lib/api/resources";

export function useOrganizationSave(organizationId?: string) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useCallback(async (values: OrganizationFormValues) => {
    setError(null);
    if (!values.legalName.trim()) {
      setError(values.orgType === "individual_entrepreneur" ? "ФИО ИП обязательно." : "Полное наименование обязательно.");
      return;
    }
    setPending(true);
    try {
      const payload = buildOrganizationPayload(values);
      if (organizationId) {
        await updateOrganization(organizationId, payload);
        router.push(`/organizations/${organizationId}`);
      } else {
        const organization = await createOrganization(payload);
        router.replace(`/organizations/${organization.id}`);
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Не удалось сохранить организацию.");
    } finally {
      setPending(false);
    }
  }, [organizationId, router]);

  return { pending, error, save };
}
