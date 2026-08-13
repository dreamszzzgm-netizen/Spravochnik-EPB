"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { identifierTypesFor, type OrganizationFormValues } from "@/components/organization-form-model";
import type { IdentifierType, OrganizationType } from "@/lib/api/types";

const ORG_TYPES: { value: OrganizationType; label: string }[] = [
  { value: "legal_entity", label: "Юридическое лицо" },
  { value: "individual_entrepreneur", label: "Индивидуальный предприниматель" },
  { value: "branch", label: "Филиал" },
];

interface Props {
  values: OrganizationFormValues;
  disabled: boolean;
  setText: (field: Exclude<keyof OrganizationFormValues, "orgType" | "identifiers">, value: string) => void;
  setType: (value: OrganizationType) => void;
  setIdentifier: (type: IdentifierType, value: string) => void;
}

export function OrganizationFormFields({ values, disabled, setText, setType, setIdentifier }: Props) {
  const isIp = values.orgType === "individual_entrepreneur";
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
        <Label htmlFor="comment">Примечание</Label>
        <Textarea id="comment" value={values.comment} onChange={(e) => setText("comment", e.target.value)} rows={3} disabled={disabled} />
      </div>
    </div>
  );
}
