"use client";

import { useCallback, useState } from "react";
import { ScanText, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import {
  previewOrganizationImport,
  previewOrganizationImportFile,
} from "@/lib/api/resources";
import type { OrganizationImportPreviewResponse } from "@/lib/api/types";

interface OrganizationSmartImportProps {
  disabled?: boolean;
  onApply: (preview: OrganizationImportPreviewResponse) => void;
}

export function OrganizationSmartImport({ disabled = false, onApply }: OrganizationSmartImportProps) {
  const [importText, setImportText] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<OrganizationImportPreviewResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runPreview = useCallback(async (loader: () => Promise<OrganizationImportPreviewResponse>) => {
    setError(null);
    setPending(true);
    try {
      setPreview(await loader());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Не удалось распознать реквизиты.");
    } finally {
      setPending(false);
    }
  }, []);

  const previewText = useCallback(() => {
    void runPreview(() => previewOrganizationImport(importText));
  }, [importText, runPreview]);

  const previewFile = useCallback(() => {
    if (!importFile) return;
    void runPreview(() => previewOrganizationImportFile(importFile));
  }, [importFile, runPreview]);

  const apply = useCallback(() => {
    if (!preview) return;
    onApply(preview);
    setPreview(null);
  }, [onApply, preview]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ScanText className="h-5 w-5" aria-hidden="true" />
          Умный импорт реквизитов
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Вставьте текст или выберите файл карточки предприятия. Обработка выполняется локально;
          результат сначала показывается для проверки и не записывается автоматически.
        </p>
        <Textarea
          value={importText}
          onChange={(event) => setImportText(event.target.value)}
          placeholder="Вставьте реквизиты организации или ИП…"
          rows={5}
          disabled={pending || disabled}
        />
        <Button
          type="button"
          variant="outline"
          onClick={previewText}
          disabled={pending || disabled || importText.trim().length < 10}
        >
          {pending ? "Распознаю…" : "Распознать текст"}
        </Button>

        <div className="rounded-lg border p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium">
            <Upload className="h-4 w-4" aria-hidden="true" />
            Импорт из файла
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-2">
              <Label htmlFor="organization_import_file">Файл реквизитов</Label>
              <Input
                id="organization_import_file"
                type="file"
                accept=".txt,.docx,.xlsx,.pdf,.png,.jpg,.jpeg"
                onChange={(event) => setImportFile(event.target.files?.[0] ?? null)}
                disabled={pending || disabled}
              />
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={previewFile}
              disabled={!importFile || pending || disabled}
            >
              Распознать файл
            </Button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            TXT, DOCX, XLSX и PDF с текстовым слоем обрабатываются локально. Для изображений и
            сканированных PDF нужен локальный OCR; внешний OCR не используется.
          </p>
        </div>

        {error && <p className="text-sm text-destructive" role="alert">{error}</p>}

        {preview && (
          <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
            <div>
              <p className="text-sm font-medium">Предварительный просмотр</p>
              <p className="text-sm text-muted-foreground">
                {preview.candidate.legal_name || "Наименование не распознано"}
              </p>
            </div>
            {preview.candidate.identifiers.length > 0 && (
              <div className="flex flex-wrap gap-2 text-xs">
                {preview.candidate.identifiers.map((identifier) => (
                  <span key={identifier.identifier_type} className="rounded-full bg-secondary px-2 py-1">
                    {identifier.identifier_type.toUpperCase()}: {identifier.identifier_value}
                  </span>
                ))}
              </div>
            )}
            {[...preview.warnings, ...preview.duplicate_warnings].map((warning) => (
              <p key={warning} className="text-sm text-destructive">{warning}</p>
            ))}
            <Button type="button" onClick={apply}>Применить к форме</Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
