"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Building2, FileText, ListTodo, ShieldCheck } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import { getManagementReport, type ManagementReportResponse } from "@/lib/api/resources";

function MetricValue({ value }: { value: number | undefined }) {
  return <p className="text-3xl font-semibold tabular-nums">{value ?? "—"}</p>;
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

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center gap-3 space-y-0">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
              <Building2 className="h-5 w-5" aria-hidden="true" />
            </div>
            <CardTitle className="text-base">Организации</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <MetricValue value={report?.organizations_total} />
            <p className="text-sm text-muted-foreground">Активных карточек организаций</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-3 space-y-0">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
              <FileText className="h-5 w-5" aria-hidden="true" />
            </div>
            <CardTitle className="text-base">Договоры в работе</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <MetricValue value={report?.contracts.active} />
            <p className="text-sm text-muted-foreground">
              Всего: {report?.contracts.total ?? "—"} · завершено: {report?.contracts.completed ?? "—"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-3 space-y-0">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
              <ListTodo className="h-5 w-5" aria-hidden="true" />
            </div>
            <CardTitle className="text-base">Просроченные задачи</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <MetricValue value={report?.tasks.overdue} />
            <p className="text-sm text-muted-foreground">
              Всего: {report?.tasks.total ?? "—"} · выполнено: {report?.tasks.completed ?? "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-5 w-5" aria-hidden="true" />
              Контроль документов
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="font-medium">Источник документов ещё не подключён</p>
            <p className="text-sm text-muted-foreground">
              После подключения домена документов здесь появятся просроченные, истекающие,
              отсутствующие документы и документы без указанного срока действия.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              Экспертизы
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="font-medium">Источник экспертиз ещё не подключён</p>
            <p className="text-sm text-muted-foreground">
              Раздел начнёт показывать реальные показатели после появления backend-домена
              экспертиз в интеграционной базе.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
