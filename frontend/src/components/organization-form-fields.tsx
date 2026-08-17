"use client";

import { useCallback, useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { identifierTypesFor, type OrganizationFormValues } from "@/components/organization-form-model";
import type { IdentifierType, OrganizationParentSearchResult, OrganizationType } from "@/lib/api/types";

const ORG_TYPES: { value: OrganizationType; label: string }[] = [
  { value: "legal_entity", label: "Юридическое лицо" },
  { value: "individual_entrepreneur", label: "Индивидуальный предприниматель" },
  { value: "branch", label: "Филиал" },
];

interface Props {
  values: OrganizationFormValues;
  disabled: boolean;
  setText: (field: Exclude<keyof OrganizationFormValues, "orgType" | "identifiers" | "parentId">, value: string) => void;
  setType: (value: OrganizationType) => void;
  setIdentifier: (type: IdentifierType, value: string) => void;
  setParentId: (value: string) => void;
}

export function OrganizationFormFields({ values, disabled, setText, setType, setIdentifier, setParentId }: Props) {
  const isIp = values.orgType === "individual_entrepreneur";
  const isBranch = values.orgType === "branch";
  const [parentSearch, setParentSearch] = useState("");
  const [parentResults, setParentResults] = useState<OrganizationParentSearchResult[]>([]);
  const [parentLoading, setParentLoading] = useState(false);
  const [selectedParent, setSelectedParent] = useState<OrganizationParentSearchResult | null>(null);

  const searchParents = useCallback(async (q: string) => {
    if (q.length < 2) {
      setParentResults([]);
      return;
    }
    setParentLoading(true);
    try {
      const res = await fetch(`/api/organizations/search?q=${encodeURIComponent(q)}&page_size=10`);
      if (res.ok) {
        const data = await res.json();
        setParentResults(data);
      }
    } finally {
      setParentLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => searchParents(parentSearch), 300);
    return () => clearTimeout(timer);
  }, [parentSearch, searchParents]);

  useEffect(() => {
    if (values.parentId && !selectedParent) {
      fetch(`/api/organizations/${values.parentId}`)
        .then((res) => res.ok ? res.json() : null)
        .then((data) => {
          if (data) {
            setSelectedParent({ id: data.id, legal_name: data.legal_name, short_name: data.short_name, organization_type: data.organization_type });
          }
        })
        .catch(() => {});
    }
  }, [values.parentId, selectedParent]);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="legal_name">{isIp ? "ФИО ИП *" : "Полное наименование *"}</Label>
          <Input id="legal_name" value={values.legalName} onChange={(e) => setText("legalName", e.target.value)} required maxLength={255} disabled={disabled} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="short_name">Краткое наименование</Label>
          <Input id="short_name" value={values.shortName} onChange={(e) => setText("shortName", e.target.value)} maxLength={120} disabled={disabled} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="org_type">Тип организации</Label>
          <Select value={values.orgType} onValueChange={(value) => setType(value as OrganizationType)}>
            <SelectTrigger id="org_type"><SelectValue /></SelectTrigger>
            <SelectContent>{ORG_TYPES.map((type) => <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>)}</SelectContent>
          </Select>
        </div>

        {isBranch && (
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="parent_search">Головная организация *</Label>
            {selectedParent ? (
              <div className="flex items-center gap-2 rounded border p-2">
                <span className="flex-1 text-sm">{selectedParent.legal_name}</span>
                <button
                  type="button"
                  className="text-sm text-destructive hover:underline"
                  onClick={() => {
                    setSelectedParent(null);
                    setParentId("");
                    setParentSearch("");
                  }}
                  disabled={disabled}
                >
                  Убрать
                </button>
              </div>
            ) : (
              <>
                <Input
                  id="parent_search"
                  value={parentSearch}
                  onChange={(e) => setParentSearch(e.target.value)}
                  placeholder="Введите для поиска..."
                  disabled={disabled}
                />
                {parentLoading && <p className="text-xs text-muted-foreground">Поиск...</p>}
                {parentResults.length > 0 && (
                  <div className="rounded border bg-popover text-sm max-h-48 overflow-y-auto">
                    {parentResults.map((org) => (
                      <button
                        key={org.id}
                        type="button"
                        className="w-full px-3 py-2 text-left hover:bg-accent hover:text-accent-foreground"
                        onClick={() => {
                          setSelectedParent(org);
                          setParentId(org.id);
                          setParentSearch("");
                          setParentResults([]);
                        }}
                      >
                        {org.legal_name}
                        {org.short_name ? ` (${org.short_name})` : ""}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {isIp ? (
          <>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="residence_address">Место жительства</Label>
              <Input id="residence_address" value={values.residenceAddress} onChange={(e) => setText("residenceAddress", e.target.value)} maxLength={500} disabled={disabled} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="passport_details">Паспортные данные</Label>
              <Textarea id="passport_details" value={values.passportDetails} onChange={(e) => setText("passportDetails", e.target.value)} rows={3} maxLength={2000} disabled={disabled} />
            </div>
          </>
        ) : (
          <>
            <div className="space-y-2"><Label htmlFor="director_name">Директор</Label><Input id="director_name" value={values.directorName} onChange={(e) => setText("directorName", e.target.value)} maxLength={255} disabled={disabled} /></div>
            <div className="space-y-2 sm:col-span-2"><Label htmlFor="legal_address">Юридический адрес</Label><Input id="legal_address" value={values.legalAddress} onChange={(e) => setText("legalAddress", e.target.value)} maxLength={500} disabled={disabled} /></div>
            <div className="space-y-2 sm:col-span-2"><Label htmlFor="actual_address">Фактический адрес</Label><Input id="actual_address" value={values.actualAddress} onChange={(e) => setText("actualAddress", e.target.value)} maxLength={500} disabled={disabled} /></div>
          </>
        )}

        <div className="space-y-2"><Label htmlFor="phone">Телефон</Label><Input id="phone" type="tel" value={values.phone} onChange={(e) => setText("phone", e.target.value)} maxLength={64} disabled={disabled} /></div>
        <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" value={values.email} onChange={(e) => setText("email", e.target.value)} maxLength={320} disabled={disabled} /></div>
      </div>

      <div>
        <p className="mb-2 text-sm font-medium">Реквизиты</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {identifierTypesFor(values.orgType).map((type) => (
            <div key={type} className="space-y-1.5">
              <Label htmlFor={`ident_${type}`}>{type.toUpperCase()}</Label>
              <Input id={`ident_${type}`} value={values.identifiers[type] || ""} onChange={(e) => setIdentifier(type, e.target.value)} maxLength={40} disabled={disabled} />
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="bank_details">Банковские реквизиты</Label>
        <Textarea id="bank_details" value={values.bankDetails} onChange={(e) => setText("bankDetails", e.target.value)} rows={3} maxLength={5000} disabled={disabled} />
      </div>

      <div className="space-y-2">
        <Label htmlFor="comment">Примечание</Label>
        <Textarea id="comment" value={values.comment} onChange={(e) => setText("comment", e.target.value)} rows={3} disabled={disabled} />
      </div>
    </div>
  );
}
