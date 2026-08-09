"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiError } from "@/lib/api/errors";
import { getOrganization, getOrganizationIdentifiers, updateOrganization } from "@/lib/api/resources";
import type { OrganizationType, IdentifierType } from "@/lib/api/types";

const ORG_TYPES: { value: OrganizationType; label: string }[] = [
  { value: "legal_entity", label: "Юридическое лицо" },
  { value: "individual_entrepreneur", label: "Индивидуальный предприниматель" },
  { value: "branch", label: "Филиал" },
];

const IDENTIFIER_TYPES: IdentifierType[] = ["inn", "kpp", "ogrn", "ogrnip"];

export default function EditOrganizationPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [legalName, setLegalName] = useState("");
  const [shortName, setShortName] = useState("");
  const [orgType, setOrgType] = useState<OrganizationType>("legal_entity");
  const [legalAddress, setLegalAddress] = useState("");
  const [actualAddress, setActualAddress] = useState("");
  const [directorName, setDirectorName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [comment, setComment] = useState("");
  const [identifiers, setIdentifiers] = useState<Record<IdentifierType, string>>(
    {} as Record<IdentifierType, string>,
  );
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    Promise.all([getOrganization(id), getOrganizationIdentifiers(id)])
      .then(([org, idents]) => {
        setLegalName(org.legal_name);
        setShortName(org.short_name ?? "");
        setOrgType(org.organization_type);
        setLegalAddress(org.legal_address ?? "");
        setActualAddress(org.actual_address ?? "");
        setDirectorName(org.director_name ?? "");
        setPhone(org.phone ?? "");
        setEmail(org.email ?? "");
        setComment(org.comment ?? "");
        const map: Record<string, string> = {};
        idents.forEach((i) => {
          map[i.identifier_type] = i.identifier_value;
        });
        setIdentifiers(map as Record<IdentifierType, string>);
      })
      .catch((e) => setLoadError(e instanceof ApiError ? e.detail : "Ошибка загрузки"))
      .finally(() => setLoading(false));
  }, [id]);

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
        const identList = IDENTIFIER_TYPES.filter((t) => identifiers[t]?.trim()).map((t) => ({
          identifier_type: t,
          identifier_value: identifiers[t].trim(),
          is_primary: t === "inn",
        }));
        await updateOrganization(id, {
          legal_name: legalName.trim(),
          short_name: shortName.trim() || null,
          organization_type: orgType,
          legal_address: legalAddress.trim() || null,
          actual_address: actualAddress.trim() || null,
          director_name: directorName.trim() || null,
          phone: phone.trim() || null,
          email: email.trim() || null,
          comment: comment.trim() || null,
          identifiers: identList,
        });
        router.push(`/organizations/${id}`);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.detail : "Не удалось сохранить изменения.",
        );
      } finally {
        setPending(false);
      }
    },
    [id, legalName, shortName, orgType, legalAddress, actualAddress, directorName, phone, email, comment, identifiers, router],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="py-20 text-center">
        <p className="text-sm text-destructive">{loadError}</p>
        <Button variant="outline" className="mt-4" asChild>
          <Link href="/organizations">Вернуться к списку</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/organizations/${id}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">
          Редактирование организации
        </h1>
      </div>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Основные сведения</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="legal_name">Полное наименование *</Label>
                <Input
                  id="legal_name"
                  value={legalName}
                  onChange={(e) => setLegalName(e.target.value)}
                  required
                  maxLength={255}
                  disabled={pending}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="short_name">Краткое наименование</Label>
                <Input
                  id="short_name"
                  value={shortName}
                  onChange={(e) => setShortName(e.target.value)}
                  maxLength={120}
                  disabled={pending}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="org_type">Тип организации</Label>
                <Select
                  value={orgType}
                  onValueChange={(v) => setOrgType(v as OrganizationType)}
                >
                  <SelectTrigger id="org_type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ORG_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="director_name">Директор</Label>
                <Input
                  id="director_name"
                  value={directorName}
                  onChange={(e) => setDirectorName(e.target.value)}
                  maxLength={255}
                  disabled={pending}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Телефон</Label>
                <Input
                  id="phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  maxLength={64}
                  disabled={pending}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  maxLength={320}
                  disabled={pending}
                />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="legal_address">Юридический адрес</Label>
                <Input
                  id="legal_address"
                  value={legalAddress}
                  onChange={(e) => setLegalAddress(e.target.value)}
                  maxLength={500}
                  disabled={pending}
                />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="actual_address">Фактический адрес</Label>
                <Input
                  id="actual_address"
                  value={actualAddress}
                  onChange={(e) => setActualAddress(e.target.value)}
                  maxLength={500}
                  disabled={pending}
                />
              </div>
            </div>

            <div>
              <p className="mb-2 text-sm font-medium">Реквизиты</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {IDENTIFIER_TYPES.map((t) => (
                  <div key={t} className="space-y-1.5">
                    <Label htmlFor={`ident_${t}`}>{t.toUpperCase()}</Label>
                    <Input
                      id={`ident_${t}`}
                      value={identifiers[t] || ""}
                      onChange={(e) =>
                        setIdentifiers((prev) => ({
                          ...prev,
                          [t]: e.target.value,
                        }))
                      }
                      maxLength={40}
                      disabled={pending}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="comment">Примечание</Label>
              <Textarea
                id="comment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                disabled={pending}
              />
            </div>

            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={pending}>
                Сохранить изменения
              </Button>
              <Button type="button" variant="outline" asChild>
                <Link href={`/organizations/${id}`}>Отмена</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
