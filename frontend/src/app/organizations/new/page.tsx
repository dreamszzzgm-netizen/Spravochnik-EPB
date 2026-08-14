"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ScanText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import { createOrganization, previewOrganizationImport } from "@/lib/api/resources";
import type {
  IdentifierType,
  OrganizationImportPreviewResponse,
  OrganizationType,
} from "@/lib/api/types";

const ORG_TYPES: { value: OrganizationType; label: string }[] = [
  { value: "legal_entity", label: "Юридическое лицо" },
  { value: "individual_entrepreneur", label: "Индивидуальный предприниматель" },
  { value: "branch", label: "Филиал" },
];

function identifierTypesFor(type: OrganizationType): IdentifierType[] {
  return type === "individual_entrepreneur" ? ["inn", "ogrnip"] : ["inn", "kpp", "ogrn"];
}

export default function NewOrganizationPage() {
  const router = useRouter();
  const [legalName, setLegalName] = useState("");
  const [shortName, setShortName] = useState("");
  const [orgType, setOrgType] = useState<OrganizationType>("legal_entity");
  const [legalAddress, setLegalAddress] = useState("");
  const [actualAddress, setActualAddress] = useState("");
  const [residenceAddress, setResidenceAddress] = useState("");
  const [directorName, setDirectorName] = useState("");
  const [passportDetails, setPassportDetails] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [comment, setComment] = useState("");
  const [identifiers, setIdentifiers] = useState<Record<IdentifierType, string>>(
    {} as Record<IdentifierType, string>,
  );
  const [importText, setImportText] = useState("");
  const [importPreview, setImportPreview] = useState<OrganizationImportPreviewResponse | null>(null);
  const [importPending, setImportPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const handlePreview = useCallback(async () => {
    setError(null);
    setImportPending(true);
    try {
      setImportPreview(await previewOrganizationImport(importText));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось распознать реквизиты.");
    } finally {
      setImportPending(false);
    }
  }, [importText]);

  const applyPreview = useCallback(() => {
    if (!importPreview) return;
    const candidate = importPreview.candidate;
    setOrgType(candidate.organization_type);
    setLegalName(candidate.legal_name ?? "");
    setShortName(candidate.short_name ?? "");
    setLegalAddress(candidate.legal_address ?? "");
    setActualAddress(candidate.actual_address ?? "");
    setResidenceAddress(candidate.residence_address ?? "");
    setDirectorName(candidate.director_name ?? "");
    setPassportDetails(candidate.passport_details ?? "");
    setPhone(candidate.phone ?? "");
    setEmail(candidate.email ?? "");
    setIdentifiers((previous) => {
      const next = { ...previous };
      for (const identifier of candidate.identifiers) {
        next[identifier.identifier_type] = identifier.identifier_value;
      }
      return next;
    });
    setImportPreview(null);
  }, [importPreview]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      if (!legalName.trim()) {
        setError("Полное наименование обязательно.");
        return;
      }
      setPending(true);
      try {
        const identifierTypes = identifierTypesFor(orgType);
        const identList = identifierTypes
          .filter((type) => identifiers[type]?.trim())
          .map((type) => ({
            identifier_type: type,
            identifier_value: identifiers[type].trim(),
            is_primary: type === "inn",
          }));
        const isIp = orgType === "individual_entrepreneur";
        const org = await createOrganization({
          legal_name: legalName.trim(),
          short_name: shortName.trim() || null,
          organization_type: orgType,
          legal_address: isIp ? null : legalAddress.trim() || null,
          actual_address: isIp ? null : actualAddress.trim() || null,
          residence_address: isIp ? residenceAddress.trim() || null : null,
          director_name: isIp ? null : directorName.trim() || null,
          passport_details: isIp ? passportDetails.trim() || null : null,
          phone: phone.trim() || null,
          email: email.trim() || null,
          comment: comment.trim() || null,
          bank_details: null,
          parent_id: null,
          identifiers: identList,
        });
        router.replace(`/organizations/${org.id}`);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Не удалось создать организацию.");
      } finally {
        setPending(false);
      }
    },
    [
      legalName,
      shortName,
      orgType,
      legalAddress,
      actualAddress,
      residenceAddress,
      directorName,
      passportDetails,
      phone,
      email,
      comment,
      identifiers,
      router,
    ],
  );

  const visibleIdentifierTypes = identifierTypesFor(orgType);
  const isIp = orgType === "individual_entrepreneur";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/organizations" aria-label="Назад к организациям">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">Новая организация</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ScanText className="h-5 w-5" />
            Умный импорт реквизитов
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Вставьте текст карточки предприятия или реквизитов. Обработка выполняется локально;
            найденные данные сначала показываются для проверки и не записываются автоматически.
          </p>
          <Textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder="Вставьте реквизиты организации или ИП…"
            rows={6}
            disabled={importPending || pending}
          />
          <Button
            type="button"
            variant="outline"
            onClick={handlePreview}
            disabled={importPending || importText.trim().length < 10}
          >
            {importPending ? "Распознаю…" : "Распознать реквизиты"}
          </Button>

          {importPreview && (
            <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
              <div>
                <p className="text-sm font-medium">Предварительный просмотр</p>
                <p className="text-sm text-muted-foreground">
                  {importPreview.candidate.legal_name || "Наименование не распознано"}
                </p>
              </div>
              {importPreview.candidate.identifiers.length > 0 && (
                <div className="flex flex-wrap gap-2 text-xs">
                  {importPreview.candidate.identifiers.map((identifier) => (
                    <span key={identifier.identifier_type} className="rounded-full bg-secondary px-2 py-1">
                      {identifier.identifier_type.toUpperCase()}: {identifier.identifier_value}
                    </span>
                  ))}
                </div>
              )}
              {[...importPreview.warnings, ...importPreview.duplicate_warnings].map((warning) => (
                <p key={warning} className="text-sm text-destructive">
                  {warning}
                </p>
              ))}
              <Button type="button" onClick={applyPreview}>
                Применить к форме
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Основные сведения</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="legal_name">Полное наименование *</Label>
                <Input id="legal_name" value={legalName} onChange={(e) => setLegalName(e.target.value)} required maxLength={255} disabled={pending} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="short_name">Краткое наименование</Label>
                <Input id="short_name" value={shortName} onChange={(e) => setShortName(e.target.value)} maxLength={120} disabled={pending} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="org_type">Тип организации</Label>
                <Select value={orgType} onValueChange={(value) => setOrgType(value as OrganizationType)}>
                  <SelectTrigger id="org_type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ORG_TYPES.map((type) => <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              {isIp ? (
                <>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="residence_address">Место жительства</Label>
                    <Input id="residence_address" value={residenceAddress} onChange={(e) => setResidenceAddress(e.target.value)} maxLength={500} disabled={pending} />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="passport_details">Паспортные данные</Label>
                    <Textarea id="passport_details" value={passportDetails} onChange={(e) => setPassportDetails(e.target.value)} rows={3} maxLength={2000} disabled={pending} />
                  </div>
                </>
              ) : (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="director_name">Директор</Label>
                    <Input id="director_name" value={directorName} onChange={(e) => setDirectorName(e.target.value)} maxLength={255} disabled={pending} />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="legal_address">Юридический адрес</Label>
                    <Input id="legal_address" value={legalAddress} onChange={(e) => setLegalAddress(e.target.value)} maxLength={500} disabled={pending} />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="actual_address">Фактический адрес</Label>
                    <Input id="actual_address" value={actualAddress} onChange={(e) => setActualAddress(e.target.value)} maxLength={500} disabled={pending} />
                  </div>
                </>
              )}

              <div className="space-y-2">
                <Label htmlFor="phone">Телефон</Label>
                <Input id="phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={64} disabled={pending} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={320} disabled={pending} />
              </div>
            </div>

            <div>
              <p className="mb-2 text-sm font-medium">Реквизиты</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {visibleIdentifierTypes.map((type) => (
                  <div key={type} className="space-y-1.5">
                    <Label htmlFor={`ident_${type}`}>{type.toUpperCase()}</Label>
                    <Input
                      id={`ident_${type}`}
                      value={identifiers[type] || ""}
                      onChange={(e) => setIdentifiers((previous) => ({ ...previous, [type]: e.target.value }))}
                      maxLength={40}
                      disabled={pending}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="comment">Примечание</Label>
              <Textarea id="comment" value={comment} onChange={(e) => setComment(e.target.value)} rows={3} disabled={pending} />
            </div>

            {error && <p className="text-sm text-destructive" role="alert">{error}</p>}

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={pending}>{pending ? "Создание…" : "Создать организацию"}</Button>
              <Button type="button" variant="outline" asChild><Link href="/organizations">Отмена</Link></Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
