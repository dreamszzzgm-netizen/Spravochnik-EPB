"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Building2,
  FileText,
  History,
  Loader2,
  ShieldCheck,
  User,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { ApiError } from "@/lib/api/errors";
import {
  EXPERTISE_STATUS_LABELS,
  getExpertise,
  getExpertiseStatusHistory,
  type ExpertiseResponse,
  type ExpertiseStatusHistoryResponse,
} from "@/lib/api/expertises";
import { ExpertiseCollaboration } from "./expertise-collaboration";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU").format(new Date(value));
}

function subjectKindLabel(kind: string | null): string {
  if (kind === "technical_device") return "Техническое устройство";
  if (kind === "building") return "Здание / сооружение";
  return "—";
}

export function ExpertiseDetail({ expertiseId }: { expertiseId: string }) {
  const [expertise, setExpertise] = useState<ExpertiseResponse | null>(null);
  const [history, setHistory] = useState<ExpertiseStatusHistoryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      setLoading(true);
      setError(null);
      Promise.all([
        getExpertise(expertiseId, { signal: controller.signal }),
        getExpertiseStatusHistory(expertiseId, { signal: controller.signal }),
      ])
        .then(([expertiseData, historyData]) => {
          setExpertise(expertiseData);
          setHistory(historyData);
        })
        .catch((caught: unknown) => {
          if (caught instanceof DOMException && caught.name === "AbortError") return;
          setError(
            caught instanceof ApiError ? caught.detail : "Не удалось загрузить экспертизу.",
          );
        })
        .finally(() => setLoading(false));
    });
    return () => controller.abort();
  }, [expertiseId]);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive" role="alert">
        {error}
      </div>
    );
  }

  if (!expertise) return null;

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground">
          <Link href="/expertise">
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            К списку экспертиз
          </Link>
        </Button>
      </div>

      <Card>
        <CardContent className="p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{subjectKindLabel(expertise.subject_kind)}</Badge>
            <StatusBadge
              status={EXPERTISE_STATUS_LABELS[expertise.status]}
              kind="expertise"
            />
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
            {expertise.subject_name ?? "Экспертиза"}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <span className="font-mono">{expertise.internal_number ?? expertise.id.slice(0, 8)}</span>
            <span>·</span>
            <span className="inline-flex items-center gap-1">
              <FileText className="h-3.5 w-3.5" />
              {expertise.contract_number ?? "—"}
            </span>
            <span>·</span>
            <span className="inline-flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5" />
              {expertise.organization_name ?? "—"}
            </span>
            <span>·</span>
            <span className="inline-flex items-center gap-1">
              <User className="h-3.5 w-3.5" />
              {expertise.responsible_expert_name ?? "—"}
            </span>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Основное</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
              <InfoRow label="Предмет экспертизы" value={expertise.subject_name ?? "—"} />
              <InfoRow label="Тип предмета" value={subjectKindLabel(expertise.subject_kind)} />
              <InfoRow label="Тип экспертизы" value={expertise.expertise_type_name ?? "—"} />
              <InfoRow label="Договор" value={expertise.contract_number ?? "—"} mono />
              <InfoRow label="Организация" value={expertise.organization_name ?? "—"} />
              <InfoRow label="Ответственный эксперт" value={expertise.responsible_expert_name ?? "—"} />
              <InfoRow label="Дата создания" value={formatDate(expertise.created_at)} />
              <InfoRow label="Версия" value={String(expertise.version)} />
            </dl>
            {expertise.comment && (
              <p className="mt-4 rounded-md border border-border/70 bg-muted/30 p-3 text-sm text-foreground">
                {expertise.comment}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <History className="h-4 w-4" />
              История статусов
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {history.length === 0 ? (
              <p className="px-4 py-6 text-sm text-muted-foreground">История пуста.</p>
            ) : (
              <ul className="divide-y divide-border">
                {history.map((row) => (
                  <li key={row.id} className="flex items-center justify-between gap-3 px-4 py-3">
                    <span className="text-sm text-foreground">
                      {row.from_status
                        ? EXPERTISE_STATUS_LABELS[row.from_status]
                        : "Создание"}{" "}
                      → {EXPERTISE_STATUS_LABELS[row.to_status]}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(row.changed_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <ExpertiseCollaboration expertiseId={expertise.id} />

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="h-4 w-4" />
            Обследование, расчёты, заключение и РТН
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Эти разделы будут подключены в следующих этапах после появления соответствующих
          backend-доменов. Сейчас доступны карточка и статусы экспертизы.
        </CardContent>
      </Card>
    </div>
  );
}

function InfoRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className={`mt-1 truncate text-sm text-foreground ${mono ? "font-mono" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
