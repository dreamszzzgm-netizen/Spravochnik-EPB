"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Building2, FileText, ListTodo, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import {
  getManagementReport,
  type DocumentControlStatus,
  type ManagementReportResponse,
} from "@/lib/api/reports";

const STATUS_LABELS: Record<DocumentControlStatus, string> = {
  expired: "Срок истёк",
  expiring_14: "Истекает ≤ 14 дней",
  expiring_40: "Истекает 15–40 дней",
  valid: "Действует",
  missing: "Не загружен",
  no_expiry: "Срок не указан",
};

function MetricValue({ value }: { value: number | undefined }) {
  return <p className="text-3xl font-semibold tabular-nums">{value ?? "—"}</p>;
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU").format(new Date(`${value}T00:00:00`));
}

export default function ReportsPage() {
  const [report, setReport] = useState<ManagementReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getManagementReport({ signal: controller.signal })
      .then(setReport)
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof ApiError ? caught.detail : "Не удалось загрузить отчёт.");
      });
    return () => controller.abort();
  }, []);

  const documents = report?.documents;
  const documentProblems = documents
    ? documents.expired + documents.expiring_14 + documents.expiring_40 + documents.missing + documents.no_expiry
    : undefined;

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Управленческий отчёт</h1>
        <p className="text-sm text-muted-foreground">
          Сводка формируется из рабочих данных системы. Демо-значения не используются.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center gap-3 space-y-0">
            <Building2 className="h-5 w-5" aria-hidden="true" />
            <CardTitle className="text-base">Организации</CardTitle>
          </CardHeader>
          <CardContent>
            <MetricValue value={report?.organizations_total} />
            <p className="text-sm text-muted-foreground">Активных карточек</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-3 space-y-0">
            <FileText className="h-5 w-5" aria-hidden="true" />
            <CardTitle className="text-base">Договоры в работе</CardTitle>
          </CardHeader>
          <CardContent>
            <MetricValue value={report?.contracts.active} />
            <p className="text-sm text-muted-foreground">
              Всего: {report?.contracts.total ?? "—"} · завершено: {report?.contracts.completed ?? "—"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-3 space-y-0">
            <ListTodo className="h-5 w-5" aria-hidden="true" />
            <CardTitle className="text-base">Просроченные задачи</CardTitle>
          </CardHeader>
          <CardContent>
            <MetricValue value={report?.tasks.overdue} />
            <p className="text-sm text-muted-foreground">Всего задач: {report?.tasks.total ?? "—"}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-3 space-y-0">
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
            <CardTitle className="text-base">Документы требуют внимания</CardTitle>
          </CardHeader>
          <CardContent>
            <MetricValue value={documents?.source_available ? documentProblems : undefined} />
            <p className="text-sm text-muted-foreground">
              {documents?.source_available ? `Всего загружено: ${documents.total}` : "Источник ещё не подключён"}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
            Контроль документов организаций
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {!documents?.source_available ? (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
              Таблицы документов и требований комплектности ещё не развернуты. После миграции этот блок автоматически начнёт показывать реальные просроченные, истекающие и отсутствующие документы.
            </div>
          ) : (
            <>
              <div className="flex flex-wrap gap-2">
                <Badge variant="destructive">Истекли: {documents.expired}</Badge>
                <Badge variant="secondary">≤ 14 дней: {documents.expiring_14}</Badge>
                <Badge variant="secondary">15–40 дней: {documents.expiring_40}</Badge>
                <Badge variant="outline">Не загружены: {documents.missing}</Badge>
                <Badge variant="outline">Без срока: {documents.no_expiry}</Badge>
              </div>

              {documents.issues.length === 0 ? (
                <p className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                  Документов, требующих внимания, сейчас нет.
                </p>
              ) : (
                <div className="overflow-x-auto rounded-md border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                      <tr>
                        <th className="px-4 py-3 font-medium">Организация</th>
                        <th className="px-4 py-3 font-medium">Документ</th>
                        <th className="px-4 py-3 font-medium">Статус</th>
                        <th className="px-4 py-3 font-medium">Срок действия</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {documents.issues.map((issue, index) => (
                        <tr key={`${issue.organization_id}-${issue.document_type}-${issue.status}-${index}`}>
                          <td className="px-4 py-3">
                            <Link className="font-medium hover:underline" href={`/organizations/${issue.organization_id}`}>
                              {issue.organization_name}
                            </Link>
                          </td>
                          <td className="px-4 py-3">{issue.document_title}</td>
                          <td className="px-4 py-3">
                            <Badge variant={issue.status === "expired" ? "destructive" : "outline"}>
                              {STATUS_LABELS[issue.status]}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 tabular-nums">{formatDate(issue.expires_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            Экспертизы
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Источник экспертиз будет подключён после появления backend-домена экспертиз в интеграционной базе.
        </CardContent>
      </Card>
    </div>
  );
}
