"use client";

import { useEffect, useMemo, useState } from "react";
import { Building2, Plus, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getOrganizations } from "@/lib/api/resources";
import type { OrganizationResponse } from "@/lib/api/types";
import { organizationName } from "@/lib/api/view-models";
import { organizationStateMessage } from "@/lib/api/state-models";

export default function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<OrganizationResponse[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [query, setQuery] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    getOrganizations({ signal: controller.signal }).then(setOrganizations).catch((caught: unknown) => {
      if (!controller.signal.aborted) setError(caught);
    });
    return () => controller.abort();
  }, []);
  const filtered = useMemo(() => (organizations || []).filter((organization) => organizationName(organization).toLocaleLowerCase("ru").includes(query.toLocaleLowerCase("ru"))), [organizations, query]);
  const message = organizationStateMessage(error, organizations, filtered.length);

  return <div className="space-y-6">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><div className="flex items-center gap-2"><h1 className="text-2xl font-semibold tracking-tight">Организации</h1><span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-400">Данные API</span></div><p className="mt-1 text-sm text-muted-foreground">Заказчики, владельцы и эксплуатирующие организации</p></div><Button size="sm" disabled title="Создание будет подключено на Stage 2"><Plus className="mr-1.5 h-4 w-4" />Новая организация</Button></div>
    <div className="relative max-w-md"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по названию…" className="pl-9" /></div>
    <Card><ul className="divide-y divide-border">{message ? <li className="px-4 py-8 text-center text-sm text-muted-foreground">{message}</li> : filtered.map((organization) => <li key={organization.id} className="flex items-center gap-4 px-4 py-4"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"><Building2 className="h-5 w-5" /></div><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{organizationName(organization)}</p><p className="mt-0.5 text-xs text-muted-foreground">{organization.organization_type} · ID {organization.id}</p></div></li>)}</ul></Card>
  </div>;
}
