"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, Loader2, Plus, Search, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { ApiError } from "@/lib/api/errors";
import { useCan } from "@/lib/auth";
import {
  EXPERTISE_STATUS_LABELS,
  getExpertises,
  type ExpertiseResponse,
  type ExpertiseStatus,
} from "@/lib/api/expertises";

const STATUS_OPTIONS: ExpertiseStatus[] = [
  "preparation",
  "document_collection",
  "inspection",
  "conclusion_preparation",
  "internal_approval",
  "ready_for_registration",
  "rtn_review",
  "rtn_rework",
  "registered",
  "received_by_customer",
  "completed",
];

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU").format(new Date(value));
}

export default function ExpertisePage() {
  const canCreate = useCan("expertises.create");
  const [items, setItems] = useState<ExpertiseResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<ExpertiseStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      setLoading(true);
      setError(null);
      getExpertises({ page, status: status || undefined }, { signal: controller.signal })
        .then((response) => {
          setItems(response.items);
          setTotal(response.total);
        })
        .catch((caught: unknown) => {
          if (caught instanceof DOMException && caught.name === "AbortError") return;
          setError(
            caught instanceof ApiError ? caught.detail : "Не удалось загрузить экспертизы.",
          );
        })
        .finally(() => setLoading(false));
    });
    return () => controller.abort();
  }, [page, status]);

  const pageSize = 20;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Экспертизы</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Экспертизы промышленной безопасности технических устройств и зданий/сооружений
          </p>
        </div>
        {canCreate && (
          <Button size="sm" asChild>
            <Link href="/expertise/new">
              <Plus className="mr-1.5 h-4 w-4" />
              Создать экспертизу
            </Link>
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative max-w-md flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Поиск по номеру экспертизы…" className="pl-9" disabled />
        </div>
        <select
          aria-label="Фильтр по статусу"
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as ExpertiseStatus | "");
            setPage(1);
          }}
        >
          <option value="">Все статусы</option>
          {STATUS_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {EXPERTISE_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Экспертизы ещё не созданы.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {items.map((expertise) => (
                <li key={expertise.id}>
                  <Link
                    href={`/expertise/${expertise.id}`}
                    className="flex items-center gap-4 px-4 py-4 transition-colors hover:bg-muted/40"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                      <ShieldCheck className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-mono text-sm font-medium text-foreground">
                          {expertise.internal_number ?? expertise.id.slice(0, 8)}
                        </p>
                        <StatusBadge
                          status={EXPERTISE_STATUS_LABELS[expertise.status]}
                          kind="expertise"
                        />
                      </div>
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {expertise.subject_name ?? "Предмет не указан"} ·{" "}
                        {expertise.organization_name ?? "—"} ·{" "}
                        {expertise.contract_number ?? "—"} ·{" "}
                        {expertise.responsible_expert_name ?? "—"}
                      </p>
                    </div>
                    <div className="hidden text-right text-xs text-muted-foreground sm:block">
                      {formatDate(expertise.updated_at)}
                    </div>
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Всего: {total}</span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Назад
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Вперёд
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
