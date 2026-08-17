"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Upload,
  FileSpreadsheet,
  Loader2,
  RefreshCw,
  SkipForward,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api/errors";
import {
  createImportSession,
  uploadImportExcel,
  getImportCandidates,
  confirmImportSession,
  getImportReport,
  updateImportCandidate,
} from "@/lib/api/resources";
import type {
  ImportSessionResponse,
  ImportCandidateResponse,
  ImportReportResponse,
  CandidateAction,
} from "@/lib/api/types";
import { useCan } from "@/lib/auth";

type WizardStep = "upload" | "preview" | "confirming" | "completed" | "failed";

const STATUS_LABELS: Record<string, string> = {
  new: "Будут добавлены",
  update: "Будут обновлены",
  potential_duplicate: "Возможные дубликаты",
  conflict: "Конфликты",
  error: "Ошибки",
  skip: "Пропустить",
};

const STATUS_COLORS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  new: "default",
  update: "secondary",
  potential_duplicate: "outline",
  conflict: "destructive",
  error: "destructive",
  skip: "outline",
};

export default function ImportPage() {
  const canImport = useCan("organizations.import");
  const [step, setStep] = useState<WizardStep>("upload");
  const [session, setSession] = useState<ImportSessionResponse | null>(null);
  const [candidates, setCandidates] = useState<ImportCandidateResponse[]>([]);
  const [report, setReport] = useState<ImportReportResponse | null>(null);
  const [uploading, setUploading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeGroup, setActiveGroup] = useState("new");

  const loadCandidates = useCallback(async (sessionId: string) => {
    const items = await getImportCandidates(sessionId);
    setCandidates(items);
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      const sess = await createImportSession();
      const updated = await uploadImportExcel(sess.id, file);
      setSession(updated);

      if (updated.status === "preview_ready") {
        await loadCandidates(updated.id);
        setStep("preview");
      } else if (updated.status === "failed") {
        setStep("failed");
        setError("Обработка файла завершилась ошибкой");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Ошибка загрузки файла");
    } finally {
      setUploading(false);
    }
  };

  const handleCandidateAction = async (
    candidateId: string,
    action: CandidateAction,
  ) => {
    if (!session) return;
    try {
      await updateImportCandidate(session.id, candidateId, { proposed_action: action });
      await loadCandidates(session.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Ошибка обновления");
    }
  };

  const handleConfirm = async () => {
    if (!session) return;
    setConfirming(true);
    setError(null);

    try {
      const result = await confirmImportSession(session.id);
      setSession(result);

      if (result.status === "completed") {
        const reportData = await getImportReport(session.id);
        setReport(reportData);
        setStep("completed");
      } else {
        setStep("failed");
        setError("Импорт завершился с ошибками");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Ошибка подтверждения");
      setStep("failed");
    } finally {
      setConfirming(false);
    }
  };

  const handleReset = () => {
    setStep("upload");
    setSession(null);
    setCandidates([]);
    setReport(null);
    setError(null);
  };

  const grouped = {
    new: candidates.filter((c) => c.candidate_status === "new"),
    update: candidates.filter((c) => c.candidate_status === "update"),
    potential_duplicate: candidates.filter((c) => c.candidate_status === "potential_duplicate"),
    conflict: candidates.filter((c) => c.candidate_status === "conflict"),
    error: candidates.filter((c) => c.candidate_status === "error"),
    skip: candidates.filter((c) => c.candidate_status === "skip"),
  };

  const actionableCount = candidates.filter(
    (c) => c.proposed_action !== "skip",
  ).length;

  if (!canImport) {
    return (
      <div className="py-20 text-center text-sm text-muted-foreground">
        У вас нет прав для импорта организаций.
      </div>
    );
  }

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
            <FileSpreadsheet className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Импорт организаций
            </h1>
            <p className="text-sm text-muted-foreground">
              Загрузка Excel-файла с данными организаций
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {step === "upload" && (
        <Card>
          <CardHeader>
            <CardTitle>Загрузка файла</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Загрузите Excel-файл (.xlsx) с данными организаций. Первая строка — заголовки
              колонок, остальные строки — данные организаций.
            </p>
            <div className="rounded-md border-2 border-dashed p-8 text-center">
              {uploading ? (
                <div className="flex flex-col items-center gap-2">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Загрузка и обработка...</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <Upload className="h-8 w-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    Выберите файл или перетащите его сюда
                  </p>
                  <input
                    type="file"
                    accept=".xlsx"
                    onChange={handleFileUpload}
                    className="cursor-pointer text-sm"
                  />
                </div>
              )}
            </div>
            <div className="rounded-md bg-muted p-3 text-xs text-muted-foreground">
              <p className="font-medium">Поддерживаемые заголовки колонок:</p>
              <p className="mt-1">
                Наименование / Полное наименование, Краткое наименование, Тип, ИНН, КПП, ОГРН,
                ОГРНИП, Юридический адрес, Фактический адрес, Директор, Телефон, Email,
                Банковские реквизиты
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {(step === "preview" || step === "confirming") && session && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Предпросмотр ({candidates.length} строк)</span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleReset}>
                    <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                    Заново
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleConfirm}
                    disabled={confirming || actionableCount === 0}
                  >
                    {confirming ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    Подтвердить импорт ({actionableCount})
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs value={activeGroup} onValueChange={setActiveGroup}>
                <TabsList>
                  {Object.entries(grouped).map(([key, items]) =>
                    items.length > 0 ? (
                      <TabsTrigger key={key} value={key}>
                        {STATUS_LABELS[key]} ({items.length})
                      </TabsTrigger>
                    ) : null,
                  )}
                </TabsList>

                {Object.entries(grouped).map(([key, items]) =>
                  items.length > 0 ? (
                    <TabsContent key={key} value={key} className="mt-4">
                      <div className="space-y-2">
                        {items.map((candidate) => (
                          <CandidateRow
                            key={candidate.id}
                            candidate={candidate}
                            onAction={handleCandidateAction}
                          />
                        ))}
                      </div>
                    </TabsContent>
                  ) : null,
                )}
              </Tabs>
            </CardContent>
          </Card>
        </>
      )}

      {step === "completed" && report && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              Импорт завершён
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Всего кандидатов" value={report.session.candidate_count} />
              <StatCard label="Добавлено" value={report.session.added_count} variant="success" />
              <StatCard label="Обновлено" value={report.session.updated_count} variant="default" />
              <StatCard label="Ошибки" value={report.session.error_count} variant="danger" />
            </div>

            <div className="rounded-md border p-4">
              <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                Детали по строкам
              </p>
              <div className="space-y-1">
                {report.candidates.map((c) => {
                const name = (c.normalized_data?.legal_name as string) || "—";
                return (
                  <div
                    key={c.id}
                    className="flex items-center justify-between text-sm"
                  >
                    <span>
                      Строка {c.row_number}: {name}
                    </span>
                    <Badge variant={STATUS_COLORS[c.candidate_status] || "outline"}>
                      {STATUS_LABELS[c.candidate_status] || c.candidate_status}
                    </Badge>
                  </div>
                );
              })}
              </div>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" asChild>
                <Link href="/organizations">К списку организаций</Link>
              </Button>
              <Button onClick={handleReset}>Новый импорт</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {step === "failed" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-destructive" />
              Ошибка импорта
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {error || "Импорт завершился с ошибками. Проверьте файл и попробуйте снова."}
            </p>
            <Button onClick={handleReset}>Попробовать снова</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function CandidateRow({
  candidate,
  onAction,
}: {
  candidate: ImportCandidateResponse;
  onAction: (id: string, action: CandidateAction) => void;
}) {
  const data = (candidate.normalized_data || {}) as Record<string, string | null | undefined>;
  const errors = candidate.validation_errors || [];
  const warnings = candidate.warnings || [];

  return (
    <div className="rounded-md border p-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              Строка {candidate.row_number}
            </span>
            <Badge variant={STATUS_COLORS[candidate.candidate_status] || "outline"}>
              {STATUS_LABELS[candidate.candidate_status]}
            </Badge>
            {candidate.matched_organization_id && (
              <Badge variant="secondary">ID: {candidate.matched_organization_id.slice(0, 8)}</Badge>
            )}
          </div>
          <p className="mt-1 text-sm font-medium">
            {data.legal_name || "Без наименования"}
          </p>
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
            {data.organization_type && <span>{String(data.organization_type)}</span>}
            {data.inn && <span>ИНН: {String(data.inn)}</span>}
            {data.kpp && <span>КПП: {String(data.kpp)}</span>}
            {data.ogrn && <span>ОГРН: {String(data.ogrn)}</span>}
            {data.ogrnip && <span>ОГРНИП: {String(data.ogrnip)}</span>}
          </div>
          {errors.length > 0 && (
            <div className="mt-2">
              {errors.map((err, i) => (
                <p key={i} className="text-xs text-destructive">
                  {err}
                </p>
              ))}
            </div>
          )}
          {warnings.length > 0 && (
            <div className="mt-2">
              {warnings.map((warn, i) => (
                <p key={i} className="text-xs text-yellow-600 dark:text-yellow-400">
                  {warn}
                </p>
              ))}
            </div>
          )}
        </div>
        <div className="flex gap-1">
          {candidate.candidate_status !== "error" && (
            <>
              {candidate.proposed_action !== "create" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onAction(candidate.id, "create")}
                >
                  Создать
                </Button>
              )}
              {candidate.proposed_action !== "update" && candidate.matched_organization_id && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onAction(candidate.id, "update")}
                >
                  Обновить
                </Button>
              )}
              {candidate.proposed_action !== "skip" && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onAction(candidate.id, "skip")}
                >
                  <SkipForward className="h-3.5 w-3.5" />
                </Button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  variant = "default",
}: {
  label: string;
  value: number;
  variant?: "default" | "success" | "danger";
}) {
  const colorClass =
    variant === "success"
      ? "text-green-600"
      : variant === "danger"
        ? "text-destructive"
        : "text-foreground";

  return (
    <div className="rounded-md border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-2xl font-semibold ${colorClass}`}>{value}</p>
    </div>
  );
}
