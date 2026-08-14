"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Building2, FileText, Loader2, Pencil, CheckCircle2, AlertTriangle, Info, Landmark } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { ApiError } from "@/lib/api/errors";
import { getOrganization, getOrganizationIdentifiers, getOrganizationCompleteness } from "@/lib/api/resources";
import type { OrganizationResponse, OrganizationIdentifierResponse, OrganizationCompletenessResponse } from "@/lib/api/types";
import { organizationName, organizationTypeLabel } from "@/lib/api/view-models";
import { useCan } from "@/lib/auth";
import { OrganizationContacts } from "./_components/organization-contacts";
import { OrganizationOpoList } from "./_components/organization-opo-list";
import { OrganizationDeviceList } from "./_components/organization-device-list";
import { OrganizationBuildingList } from "./_components/organization-building-list";

export default function OrganizationWorkspacePage() {
  const params = useParams();
  const id = params.id as string;
  const [org, setOrg] = useState<OrganizationResponse | null>(null);
  const [identifiers, setIdentifiers] = useState<OrganizationIdentifierResponse[]>([]);
  const [completeness, setCompleteness] = useState<OrganizationCompletenessResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const canEdit = useCan("organizations.update");

  useEffect(() => {
    Promise.all([getOrganization(id), getOrganizationIdentifiers(id), getOrganizationCompleteness(id)])
      .then(([o, i, c]) => {
        setOrg(o);
        setIdentifiers(i);
        setCompleteness(c);
      })
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Ошибка загрузки"))
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
    identifiers.map((i) => [i.identifier_type, i.identifier_value]),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/organizations">
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
        {completeness && (
          <Badge
            variant={
              completeness.status === "complete"
                ? "default"
                : completeness.status === "needs_attention"
                  ? "secondary"
                  : "destructive"
            }
            className="ml-2"
          >
            {completeness.status === "complete" && (
              <><CheckCircle2 className="mr-1 h-3 w-3" />Заполнено</>
            )}
            {completeness.status === "needs_attention" && (
              <><AlertTriangle className="mr-1 h-3 w-3" />Требует внимания</>
            )}
            {completeness.status === "missing_required" && (
              <><AlertTriangle className="mr-1 h-3 w-3" />Есть обязательные незаполненные поля</>
            )}
          </Badge>
        )}
        <div className="ml-auto flex gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/organizations/${id}/documents`}>
              <FileText className="mr-1.5 h-4 w-4" />
              Документы
            </Link>
          </Button>
          {canEdit && (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/organizations/${id}/edit`}>
              <Pencil className="mr-1.5 h-4 w-4" />
              Редактировать
            </Link>
          </Button>
          )}
        </div>
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

        <TabsContent value="general" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Общие сведения</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-4 sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-muted-foreground">Полное наименование</dt>
                  <dd className="text-sm font-medium">{org.legal_name}</dd>
                </div>
                {org.short_name && (
                  <div>
                    <dt className="text-xs text-muted-foreground">Краткое наименование</dt>
                    <dd className="text-sm font-medium">{org.short_name}</dd>
                  </div>
                )}
                {org.director_name && (
                  <div>
                    <dt className="text-xs text-muted-foreground">Директор</dt>
                    <dd className="text-sm font-medium">{org.director_name}</dd>
                  </div>
                )}
                {org.phone && (
                  <div>
                    <dt className="text-xs text-muted-foreground">Телефон</dt>
                    <dd className="text-sm font-medium">{org.phone}</dd>
                  </div>
                )}
                {org.email && (
                  <div>
                    <dt className="text-xs text-muted-foreground">Email</dt>
                    <dd className="text-sm font-medium">{org.email}</dd>
                  </div>
                )}
                {org.legal_address && (
                  <div className="sm:col-span-2">
                    <dt className="text-xs text-muted-foreground">Юридический адрес</dt>
                    <dd className="text-sm font-medium">{org.legal_address}</dd>
                  </div>
                )}
                {org.actual_address && (
                  <div className="sm:col-span-2">
                    <dt className="text-xs text-muted-foreground">Фактический адрес</dt>
                    <dd className="text-sm font-medium">{org.actual_address}</dd>
                  </div>
                )}
              </dl>
              {(identMap.inn || identMap.kpp || identMap.ogrn || identMap.ogrnip) && (
                <div className="mt-6">
                  <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                    Реквизиты
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {identMap.inn && (
                      <Badge variant="secondary">ИНН {identMap.inn}</Badge>
                    )}
                    {identMap.kpp && (
                      <Badge variant="secondary">КПП {identMap.kpp}</Badge>
                    )}
                    {identMap.ogrn && (
                      <Badge variant="secondary">ОГРН {identMap.ogrn}</Badge>
                    )}
                    {identMap.ogrnip && (
                      <Badge variant="secondary">ОГРНИП {identMap.ogrnip}</Badge>
                    )}
                  </div>
                </div>
              )}
              {org.comment && (
                <div className="mt-4">
                  <dt className="text-xs text-muted-foreground">Примечание</dt>
                  <dd className="text-sm">{org.comment}</dd>
                </div>
              )}
              {org.bank_details && (
                <div className="mt-4">
                  <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground flex items-center gap-1">
                    <Landmark className="h-3 w-3" />Банковские реквизиты
                  </p>
                  <pre className="rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">{org.bank_details}</pre>
                </div>
              )}
              {completeness && completeness.missing_required_fields.length > 0 && (
                <div className="mt-6 rounded-md border border-destructive/20 bg-destructive/5 p-4">
                  <p className="mb-2 text-xs font-semibold uppercase text-destructive">
                    Обязательные незаполненные поля
                  </p>
                  <ul className="list-inside list-disc space-y-1">
                    {completeness.missing_required_fields.map((f) => (
                      <li key={f.code} className="text-sm text-muted-foreground">
                        {f.label}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {completeness && completeness.status === "needs_attention" && completeness.warning_fields.length > 0 && (
                <div className="mt-4 rounded-md border border-yellow-200 bg-yellow-50 p-4 dark:border-yellow-800 dark:bg-yellow-950">
                  <p className="mb-2 text-xs font-semibold uppercase text-yellow-700 dark:text-yellow-300 flex items-center gap-1">
                    <Info className="h-3 w-3" />Рекомендации
                  </p>
                  <ul className="list-inside list-disc space-y-1">
                    {completeness.warning_fields.map((f) => (
                      <li key={f.code} className="text-sm text-muted-foreground">
                        {f.label}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
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

        {["contracts"].map((tab) => (
          <TabsContent key={tab} value={tab} className="mt-4">
            <Card>
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                Раздел будет подключён на следующем этапе
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
