"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, FileUp, Loader2, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/errors";
import {
  deleteOrganizationDocument,
  getOrganizationDocuments,
  organizationDocumentDownloadHref,
  type OrganizationDocumentResponse,
  uploadOrganizationDocument,
} from "@/lib/api/documents";
import { useCan } from "@/lib/auth";

function formatBytes(value: number) {
  if (value < 1024) return `${value} Б`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} КБ`;
  return `${(value / (1024 * 1024)).toFixed(1)} МБ`;
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU").format(new Date(`${value}T00:00:00`));
}

const STATUS_LABELS = {
  expired: "Истёк",
  expiring_14: "Истекает ≤ 14 дней",
  expiring_40: "Истекает 15–40 дней",
  valid: "Действует",
  no_expiry: "Срок не указан",
} as const;

export function OrganizationDocuments({ organizationId }: { organizationId: string }) {
  const canEdit = useCan("organizations.update");
  const [documents, setDocuments] = useState<OrganizationDocumentResponse[]>([]);
  const [sourceAvailable, setSourceAvailable] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("");
  const [title, setTitle] = useState("");
  const [issuedAt, setIssuedAt] = useState("");
  const [expiresAt, setExpiresAt] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await getOrganizationDocuments(organizationId, { signal });
      setDocuments(response.items);
      setSourceAvailable(response.source_available);
      setError(null);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(caught instanceof ApiError ? caught.detail : "Не удалось загрузить документы.");
    } finally {
      setLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => { void load(controller.signal); });
    return () => controller.abort();
  }, [load]);

  const submit = useCallback(async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !documentType.trim() || !title.trim()) return;
    setPending(true);
    setError(null);
    try {
      await uploadOrganizationDocument(organizationId, {
        file,
        documentType: documentType.trim(),
        title: title.trim(),
        issuedAt: issuedAt || undefined,
        expiresAt: expiresAt || undefined,
      });
      setFile(null);
      setDocumentType("");
      setTitle("");
      setIssuedAt("");
      setExpiresAt("");
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Не удалось загрузить документ.");
    } finally {
      setPending(false);
    }
  }, [documentType, expiresAt, file, issuedAt, load, organizationId, title]);

  const remove = useCallback(async (documentId: string) => {
    if (!window.confirm("Убрать документ из карточки организации?")) return;
    setPending(true);
    try {
      await deleteOrganizationDocument(organizationId, documentId);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Не удалось удалить документ.");
    } finally {
      setPending(false);
    }
  }, [load, organizationId]);

  if (loading) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  if (sourceAvailable === false) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Хранилище документов подготовлено в коде, но таблицы Documents ещё не развернуты миграцией.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {canEdit && (
        <Card>
          <CardHeader><CardTitle className="text-base">Добавить документ</CardTitle></CardHeader>
          <CardContent>
            <form className="grid gap-4 md:grid-cols-2" onSubmit={submit}>
              <div className="space-y-2">
                <Label htmlFor="document_type">Тип документа *</Label>
                <Input id="document_type" value={documentType} onChange={(e) => setDocumentType(e.target.value)} maxLength={120} disabled={pending} placeholder="Например: insurance_policy" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="document_title">Наименование *</Label>
                <Input id="document_title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={255} disabled={pending} placeholder="Страховой полис" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="issued_at">Дата выдачи</Label>
                <Input id="issued_at" type="date" value={issuedAt} onChange={(e) => setIssuedAt(e.target.value)} disabled={pending} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="expires_at">Действует до</Label>
                <Input id="expires_at" type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} disabled={pending} />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="document_file">Файл *</Label>
                <Input id="document_file" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} disabled={pending} />
                <p className="text-xs text-muted-foreground">До 20 МБ. Файл хранится только в локальном STORAGE_ROOT.</p>
              </div>
              <div className="md:col-span-2">
                <Button type="submit" disabled={pending || !file || !documentType.trim() || !title.trim()}>
                  <FileUp className="mr-1.5 h-4 w-4" />
                  {pending ? "Загрузка…" : "Загрузить документ"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}

      <Card>
        <CardHeader><CardTitle className="text-base">Документы организации</CardTitle></CardHeader>
        <CardContent>
          {documents.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">Документы ещё не загружены.</p>
          ) : (
            <div className="space-y-3">
              {documents.map((document) => {
                const status = document.status;
                return (
                  <div key={document.id} className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{document.title}</p>
                        <Badge variant={status === "expired" ? "destructive" : "outline"}>
                          {STATUS_LABELS[status]}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {document.document_type} · {formatBytes(document.size_bytes)} · до {formatDate(document.expires_at)}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" asChild>
                        <a href={organizationDocumentDownloadHref(organizationId, document.id)}>
                          <Download className="mr-1.5 h-4 w-4" />Скачать
                        </a>
                      </Button>
                      {canEdit && (
                        <Button variant="ghost" size="icon" onClick={() => void remove(document.id)} disabled={pending} aria-label="Удалить документ">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
