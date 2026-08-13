"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import { createOrganization, getOrganizationImportCandidate } from "@/lib/api/resources";
import type { IdentifierType, OrganizationImportCandidate, OrganizationType } from "@/lib/api/types";

const ORG_TYPES: { value: OrganizationType; label: string }[] = [
  { value: "legal_entity", label: "Юридическое лицо" },
  { value: "individual_entrepreneur", label: "Индивидуальный предприниматель" },
  { value: "branch", label: "Филиал" },
];

const LEGAL_IDENTIFIERS: IdentifierType[] = ["inn", "kpp", "ogrn"];
const IP_IDENTIFIERS: IdentifierType[] = ["inn", "ogrnip"];

function valueOrEmpty(value: string | null | undefined): string {
  return value ?? "";
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
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [passportSeries, setPassportSeries] = useState("");
  const [passportNumber, setPassportNumber] = useState("");
  const [passportIssuedBy, setPassportIssuedBy] = useState("");
  const [passportIssueDate, setPassportIssueDate] = useState("");
  const [passportDepartmentCode, setPassportDepartmentCode] = useState("");
  const [bankName, setBankName] = useState("");
  const [bankBik, setBankBik] = useState("");
  const [bankAccount, setBankAccount] = useState("");
  const [correspondentAccount, setCorrespondentAccount] = useState("");
  const [comment, setComment] = useState("");
  const [identifiers, setIdentifiers] = useState<Partial<Record<IdentifierType, string>>>({});
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const [importPending, setImportPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const isLegalForm = orgType !== "individual_entrepreneur";
  const identifierTypes = orgType === "individual_entrepreneur" ? IP_IDENTIFIERS : LEGAL_IDENTIFIERS;

  const applyCandidate = useCallback((candidate: OrganizationImportCandidate) => {
    if (candidate.organization_type) setOrgType(candidate.organization_type);
    setLegalName(valueOrEmpty(candidate.legal_name));
    setShortName(valueOrEmpty(candidate.short_name));
    setLegalAddress(valueOrEmpty(candidate.legal_address));
    setActualAddress(valueOrEmpty(candidate.actual_address));
    setResidenceAddress(valueOrEmpty(candidate.residence_address));
    setDirectorName(valueOrEmpty(candidate.director_name));
    setPhone(valueOrEmpty(candidate.phone));
    setEmail(valueOrEmpty(candidate.email));
    setPassportSeries(valueOrEmpty(candidate.passport_series));
    setPassportNumber(valueOrEmpty(candidate.passport_number));
    setPassportIssuedBy(valueOrEmpty(candidate.passport_issued_by));
    setPassportIssueDate(valueOrEmpty(candidate.passport_issue_date));
    setPassportDepartmentCode(valueOrEmpty(candidate.passport_department_code));
    setBankName(valueOrEmpty(candidate.bank_name));
    setBankBik(valueOrEmpty(candidate.bank_bik));
    setBankAccount(valueOrEmpty(candidate.bank_account));
    setCorrespondentAccount(valueOrEmpty(candidate.correspondent_account));
    setIdentifiers((previous) => ({ ...previous, ...candidate.identifiers }));
    setImportWarnings(candidate.warnings);
  }, []);

  const handleImport = useCallback(async () => {
    if (!importFile) {
      setError("Выберите файл с реквизитами организации.");
      return;
    }
    setError(null);
    setImportPending(true);
    try {
      const candidate = await getOrganizationImportCandidate(importFile);
      applyCandidate(candidate);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось распознать реквизиты.");
    } finally {
      setImportPending(false);
    }
  }, [applyCandidate, importFile]);

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setError(null);
      if (!legalName.trim()) {
        setError(orgType === "individual_entrepreneur" ? "ФИО ИП обязательно." : "Полное наименование обязательно.");
        return;
      }
      setPending(true);
      try {
        const activeIdentifiers = orgType === "individual_entrepreneur" ? IP_IDENTIFIERS : LEGAL_IDENTIFIERS;
        const identList = activeIdentifiers
          .filter((type) => identifiers[type]?.trim())
          .map((type) => ({
            identifier_type: type,
            identifier_value: identifiers[type]!.trim(),
            is_primary: type === "inn",
          }));
        const isIp = orgType === "individual_entrepreneur";
        const organization = await createOrganization({
          legal_name: legalName.trim(),
          short_name: shortName.trim() || null,
          organization_type: orgType,
          legal_address: isIp ? null : legalAddress.trim() || null,
          actual_address: isIp ? null : actualAddress.trim() || null,
          residence_address: isIp ? residenceAddress.trim() || null : null,
          director_name: isIp ? null : directorName.trim() || null,
          phone: phone.trim() || null,
          email: email.trim() || null,
          passport_series: isIp ? passportSeries.trim() || null : null,
          passport_number: isIp ? passportNumber.trim() || null : null,
          passport_issued_by: isIp ? passportIssuedBy.trim() || null : null,
          passport_issue_date: isIp ? passportIssueDate || null : null,
          passport_department_code: isIp ? passportDepartmentCode.trim() || null : null,
          bank_name: bankName.trim() || null,
          bank_bik: bankBik.trim() || null,
          bank_account: bankAccount.trim() || null,
          correspondent_account: correspondentAccount.trim() || null,
          comment: comment.trim() || null,
          identifiers: identList,
        });
        router.replace(`/organizations/${organization.id}`);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Не удалось создать организацию.");
      } finally {
        setPending(false);
      }
    },
    [
      actualAddress,
      bankAccount,
      bankBik,
      bankName,
      comment,
      correspondentAccount,
      directorName,
      email,
      identifiers,
      legalAddress,
      legalName,
      orgType,
      passportDepartmentCode,
      passportIssueDate,
      passportIssuedBy,
      passportNumber,
      passportSeries,
      phone,
      residenceAddress,
      router,
      shortName,
    ],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/organizations" aria-label="К списку организаций">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Новая организация</h1>
          <p className="text-sm text-muted-foreground">Реквизиты можно заполнить вручную или через умный импорт.</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" aria-hidden="true" />
            Умный импорт
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Файл обрабатывается локально и только заполняет форму. Перед сохранением обязательно
            проверить распознанные данные.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-2">
              <Label htmlFor="organization_import">Файл с реквизитами</Label>
              <Input
                id="organization_import"
                type="file"
                accept=".txt,.pdf,.docx,.xlsx,.png,.jpg,.jpeg"
                onChange={(event) => setImportFile(event.target.files?.[0] ?? null)}
                disabled={importPending || pending}
              />
            </div>
            <Button type="button" variant="secondary" onClick={handleImport} disabled={!importFile || importPending || pending}>
              {importPending ? "Распознаём…" : "Распознать и заполнить"}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Проверить распознанные данные перед нажатием «Создать организацию».
          </p>
          {importWarnings.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
              {importWarnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Основные сведения</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="org_type">Тип организации</Label>
                <Select value={orgType} onValueChange={(value) => setOrgType(value as OrganizationType)}>
                  <SelectTrigger id="org_type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ORG_TYPES.map((type) => (
                      <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="short_name">{orgType === "individual_entrepreneur" ? "Краткое наименование" : "Сокращённое наименование"}</Label>
                <Input id="short_name" value={shortName} onChange={(event) => setShortName(event.target.value)} maxLength={120} disabled={pending} />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="legal_name">{orgType === "individual_entrepreneur" ? "ФИО индивидуального предпринимателя *" : "Полное наименование *"}</Label>
                <Input id="legal_name" value={legalName} onChange={(event) => setLegalName(event.target.value)} required maxLength={255} disabled={pending} />
              </div>

              {isLegalForm && (
                <>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="director_name">Руководитель</Label>
                    <Input id="director_name" value={directorName} onChange={(event) => setDirectorName(event.target.value)} maxLength={255} disabled={pending} />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="legal_address">Юридический адрес</Label>
                    <Input id="legal_address" value={legalAddress} onChange={(event) => setLegalAddress(event.target.value)} maxLength={500} disabled={pending} />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="actual_address">Фактический адрес</Label>
                    <Input id="actual_address" value={actualAddress} onChange={(event) => setActualAddress(event.target.value)} maxLength={500} disabled={pending} />
                  </div>
                </>
              )}

              {orgType === "individual_entrepreneur" && (
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="residence_address">Место жительства</Label>
                  <Input id="residence_address" value={residenceAddress} onChange={(event) => setResidenceAddress(event.target.value)} maxLength={500} disabled={pending} />
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="phone">Телефон</Label>
                <Input id="phone" type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} maxLength={64} disabled={pending} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} maxLength={320} disabled={pending} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Реквизиты</CardTitle></CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            {identifierTypes.map((type) => (
              <div key={type} className="space-y-2">
                <Label htmlFor={`ident_${type}`}>{type.toUpperCase()}</Label>
                <Input id={`ident_${type}`} value={identifiers[type] ?? ""} onChange={(event) => setIdentifiers((previous) => ({ ...previous, [type]: event.target.value }))} maxLength={40} disabled={pending} />
              </div>
            ))}
          </CardContent>
        </Card>

        {orgType === "individual_entrepreneur" && (
          <Card>
            <CardHeader><CardTitle>Паспортные данные</CardTitle></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2"><Label htmlFor="passport_series">Серия</Label><Input id="passport_series" value={passportSeries} onChange={(event) => setPassportSeries(event.target.value)} maxLength={16} /></div>
              <div className="space-y-2"><Label htmlFor="passport_number">Номер</Label><Input id="passport_number" value={passportNumber} onChange={(event) => setPassportNumber(event.target.value)} maxLength={32} /></div>
              <div className="space-y-2"><Label htmlFor="passport_issue_date">Дата выдачи</Label><Input id="passport_issue_date" type="date" value={passportIssueDate} onChange={(event) => setPassportIssueDate(event.target.value)} /></div>
              <div className="space-y-2"><Label htmlFor="passport_department_code">Код подразделения</Label><Input id="passport_department_code" value={passportDepartmentCode} onChange={(event) => setPassportDepartmentCode(event.target.value)} maxLength={32} /></div>
              <div className="space-y-2 sm:col-span-2"><Label htmlFor="passport_issued_by">Кем выдан</Label><Input id="passport_issued_by" value={passportIssuedBy} onChange={(event) => setPassportIssuedBy(event.target.value)} maxLength={500} /></div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader><CardTitle>Банковские реквизиты</CardTitle></CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2"><Label htmlFor="bank_name">Банк</Label><Input id="bank_name" value={bankName} onChange={(event) => setBankName(event.target.value)} maxLength={255} /></div>
            <div className="space-y-2"><Label htmlFor="bank_bik">БИК</Label><Input id="bank_bik" value={bankBik} onChange={(event) => setBankBik(event.target.value)} maxLength={20} /></div>
            <div className="space-y-2"><Label htmlFor="bank_account">Расчётный счёт</Label><Input id="bank_account" value={bankAccount} onChange={(event) => setBankAccount(event.target.value)} maxLength={64} /></div>
            <div className="space-y-2 sm:col-span-2"><Label htmlFor="correspondent_account">Корреспондентский счёт</Label><Input id="correspondent_account" value={correspondentAccount} onChange={(event) => setCorrespondentAccount(event.target.value)} maxLength={64} /></div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="space-y-2">
              <Label htmlFor="comment">Примечание</Label>
              <Textarea id="comment" value={comment} onChange={(event) => setComment(event.target.value)} rows={3} disabled={pending} />
            </div>
            {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
            <div className="flex flex-wrap gap-3">
              <Button type="submit" disabled={pending || importPending}>{pending ? "Сохраняем…" : "Создать организацию"}</Button>
              <Button type="button" variant="outline" asChild><Link href="/organizations">Отмена</Link></Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
