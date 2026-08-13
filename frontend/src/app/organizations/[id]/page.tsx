"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Building2, Loader2, Pencil } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api/errors";
import { getOrganization, getOrganizationIdentifiers } from "@/lib/api/resources";
import type { OrganizationIdentifierResponse, OrganizationResponse } from "@/lib/api/types";
import { organizationName, organizationTypeLabel } from "@/lib/api/view-models";
import { useCan } from "@/lib/auth";
import { OrganizationBuildingList } from "./_components/organization-building-list";
import { OrganizationContacts } from "./_components/organization-contacts";
import { OrganizationDeviceList } from "./_components/organization-device-list";
import { OrganizationOpoList } from "./_components/organization-opo-list";

function Detail({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  );
}

export default function OrganizationWorkspacePage() {
  const params = useParams();
  const id = params.id as string;
  const [org, setOrg] = useState<OrganizationResponse | null>(null);
  const [identifiers, setIdentifiers] = useState<OrganizationIdentifierResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const canEdit = useCan("organizations.update");

  useEffect(() => {
    Promise.all([getOrganization(id), getOrganizationIdentifiers(id)])
      .then(([organization, organizationIdentifiers]) => {
        setOrg(organization);
        setIdentifiers(organizationIdentifiers);
      })
      .catch((caught: unknown) => {
        setError(caught instanceof ApiError ? caught.detail : "Ошибка загрузки");
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !org) {
    return (
      <div className="py-20 text-center text-sm text-muted-foreground">
        {error || "Организация не найдена."}
      </div>
    );
  }

  const identMap = Object.fromEntries(
    identifiers.map((identifier) => [identifier.identifier_type, identifier.identifier_value]),
  );
  const isIp = org.organization_type === "individual_entrepreneur";
  const hasBankDetails = Boolean(
    org.bank_name || org.bank_bik || org.bank_account || org.correspondent_account,
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/organizations" aria-label="К списку организаций">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {organizationName({ short_name: org.short_name, legal_name: org.legal_name })}
            </h1>
            <p className="text-sm text-muted-foreground">
              {organizationTypeLabel(org.organization_type)}
            </p>
          </div>
        </div>
        {canEdit && (
          <Button variant="outline" size="sm" asChild className="ml-auto">
            <Link href={`/organizations/${id}/edit`}>
              <Pencil className="mr-1.5 h-4 w-4" />
              Редактировать
            </Link>
          </Button>
        )}
      </div>

      <Tabs defaultValue="general">
        <TabsList>
          <TabsTrigger value="general">Общие сведения</TabsTrigger>
          <TabsTrigger value="contacts">Контакты</TabsTrigger>
          <TabsTrigger value="opo">ОПО</TabsTrigger>
          <TabsTrigger value="devices">Тех. устройства</TabsTrigger>
          <TabsTrigger value="buildings">Здания</TabsTrigger>
          <TabsTrigger value="contracts">Договоры</TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="mt-4 space-y-4">
          <Card>
            <CardHeader><CardTitle>Общие сведения</CardTitle></CardHeader>
            <CardContent>
              <dl className="grid gap-4 sm:grid-cols-2">
                <Detail label={isIp ? "ФИО индивидуального предпринимателя" : "Полное наименование"} value={org.legal_name} />
                <Detail label="Краткое наименование" value={org.short_name} />
                {!isIp && <Detail label="Руководитель" value={org.director_name} />}
                <Detail label="Телефон" value={org.phone} />
                <Detail label="Email" value={org.email} />
                {!isIp && <Detail label="Юридический адрес" value={org.legal_address} />}
                {!isIp && <Detail label="Фактический адрес" value={org.actual_address} />}
                {isIp && <Detail label="Место жительства" value={org.residence_address} />}
              </dl>

              {(identMap.inn || identMap.kpp || identMap.ogrn || identMap.ogrnip) && (
                <div className="mt-6">
                  <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Реквизиты</p>
                  <div className="flex flex-wrap gap-2">
                    {identMap.inn && <Badge variant="secondary">ИНН {identMap.inn}</Badge>}
                    {!isIp && identMap.kpp && <Badge variant="secondary">КПП {identMap.kpp}</Badge>}
                    {!isIp && identMap.ogrn && <Badge variant="secondary">ОГРН {identMap.ogrn}</Badge>}
                    {isIp && identMap.ogrnip && <Badge variant="secondary">ОГРНИП {identMap.ogrnip}</Badge>}
                  </div>
                </div>
              )}

              {org.comment && (
                <div className="mt-4">
                  <dt className="text-xs text-muted-foreground">Примечание</dt>
                  <dd className="text-sm">{org.comment}</dd>
                </div>
              )}
            </CardContent>
          </Card>

          {org.organization_type === "individual_entrepreneur" && (
            <Card>
              <CardHeader><CardTitle>Паспортные данные</CardTitle></CardHeader>
              <CardContent>
                <dl className="grid gap-4 sm:grid-cols-2">
                  <Detail
                    label="Серия и номер"
                    value={[org.passport_series, org.passport_number].filter(Boolean).join(" ") || null}
                  />
                  <Detail label="Дата выдачи" value={org.passport_issue_date} />
                  <Detail label="Код подразделения" value={org.passport_department_code} />
                  <Detail label="Кем выдан" value={org.passport_issued_by} />
                </dl>
              </CardContent>
            </Card>
          )}

          {hasBankDetails && (
            <Card>
              <CardHeader><CardTitle>Банковские реквизиты</CardTitle></CardHeader>
              <CardContent>
                <dl className="grid gap-4 sm:grid-cols-2">
                  <Detail label="Банк" value={org.bank_name} />
                  <Detail label="БИК" value={org.bank_bik} />
                  <Detail label="Расчётный счёт" value={org.bank_account} />
                  <Detail label="Корреспондентский счёт" value={org.correspondent_account} />
                </dl>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="contacts" className="mt-4">
          <OrganizationContacts organizationId={id} />
        </TabsContent>
        <TabsContent value="opo" className="mt-4">
          <OrganizationOpoList organizationId={id} />
        </TabsContent>
        <TabsContent value="devices" className="mt-4">
          <OrganizationDeviceList organizationId={id} />
        </TabsContent>
        <TabsContent value="buildings" className="mt-4">
          <OrganizationBuildingList organizationId={id} />
        </TabsContent>
        <TabsContent value="contracts" className="mt-4">
          <Card>
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              Раздел будет подключён на следующем этапе
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
