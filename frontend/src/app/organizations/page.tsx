"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Building2, ChevronLeft, ChevronRight, Plus, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getOrganizations } from "@/lib/api/resources";
import type { OrganizationResponse } from "@/lib/api/types";
import { organizationName } from "@/lib/api/view-models";
import { organizationStateMessage } from "@/lib/api/state-models";

const PAGE_SIZE = 20;
const typeLabels: Record<string, string> = {
  legal_entity: "Юрлицо",
  individual_entrepreneur: "ИП",
  branch: "Филиал",
};

export default function OrganizationsPage() {
  const [items, setItems] = useState<OrganizationResponse[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const fetchOrganizations = useCallback(
    (controller: AbortController, q: string, p: number) => {
      getOrganizations({ q, page: p, page_size: PAGE_SIZE, signal: controller.signal })
        .then((result) => {
          setItems(result.items);
          setTotal(result.total);
          setError(null);
        })
        .catch((caught: unknown) => {
          if (!controller.signal.aborted) setError(caught);
        });
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchOrganizations(controller, search, page);
    return () => controller.abort();
  }, [search, page, fetchOrganizations]);

  function handleSearchChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearch(value);
      setPage(1);
    }, 300);
  }

  const message = organizationStateMessage(error, items, items?.length ?? 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">Организации</h1>
            <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-400">
              Данные API
            </span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Заказчики, владельцы и эксплуатирующие организации
          </p>
        </div>
        <Button size="sm" disabled title="Создание будет подключено на Stage 2">
          <Plus className="mr-1.5 h-4 w-4" />
          Новая организация
        </Button>
      </div>

      <div className="relative max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => handleSearchChange(event.target.value)}
          placeholder="Поиск по названию…"
          className="pl-9"
        />
      </div>

      <Card>
        <ul className="divide-y divide-border">
          {message ? (
            <li className="px-4 py-8 text-center text-sm text-muted-foreground">{message}</li>
          ) : (
            items!.map((organization) => (
              <li key={organization.id} className="flex items-center gap-4 px-4 py-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <Building2 className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {organizationName(organization)}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {typeLabels[organization.organization_type] ?? organization.organization_type}
                    {organization.phone ? ` · ${organization.phone}` : ""}
                  </p>
                </div>
              </li>
            ))
          )}
        </ul>

        {items && total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <span className="text-xs text-muted-foreground">
              {total} организаций · стр. {page} из {totalPages}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
