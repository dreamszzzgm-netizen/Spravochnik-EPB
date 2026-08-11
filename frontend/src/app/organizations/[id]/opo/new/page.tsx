"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import {
  createOpo,
  getActivityTypes,
  getHazardSigns,
  getOrganizations,
} from "@/lib/api/resources";
import type {
  HazardClass,
  OPOCreatePayload,
  OrganizationResponse,
  ReferenceItemResponse,
} from "@/lib/api/types";
import { organizationName } from "@/lib/api/view-models";
import { useCan } from "@/lib/auth";

const HAZARD_CLASSES: { value: HazardClass; label: string }[] = [
  { value: "hazard_class_1", label: "I класс опасности" },
  { value: "hazard_class_2", label: "II класс опасности" },
  { value: "hazard_class_3", label: "III класс опасности" },
  { value: "hazard_class_4", label: "IV класс опасности" },
];

export default function NewOpoPage() {
  const params = useParams();
  const router = useRouter();
  const organizationId = params.id as string;
  const canViewOpo = useCan("opo.view");
  const canViewOrganizations = useCan("organizations.view");

  const [name, setName] = useState("");
  const [registrationNumber, setRegistrationNumber] = useState("");
  const [hazardClass, setHazardClass] = useState<HazardClass>("hazard_class_3");
  const [address, setAddress] = useState("");
  const [registrationDate, setRegistrationDate] = useState("");
  const [ownerOrganizationId, setOwnerOrganizationId] = useState(organizationId);
  const [operatingOrganizationId, setOperatingOrganizationId] = useState(organizationId);
  const [hazardSignIds, setHazardSignIds] = useState<string[]>([]);
  const [activityTypeIds, setActivityTypeIds] = useState<string[]>([]);
  const [comment, setComment] = useState("");

  const [organizations, setOrganizations] = useState<OrganizationResponse[]>([]);
  const [hazardSigns, setHazardSigns] = useState<ReferenceItemResponse[]>([]);
  const [activityTypes, setActivityTypes] = useState<ReferenceItemResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!canViewOrganizations) return;

    const controller = new AbortController();

    getOrganizations({
      page: 1,
      page_size: 100,
      signal: controller.signal,
    })
      .then((data) => setOrganizations(data.items))
      .catch(() => setOrganizations([]));

    return () => controller.abort();
  }, [canViewOrganizations]);

  useEffect(() => {
    if (!canViewOpo) return;

    Promise.all([getHazardSigns(), getActivityTypes()])
      .then(([signs, activities]) => {
        setHazardSigns(signs);
        setActivityTypes(activities);
      })
      .catch(() => {
        setHazardSigns([]);
        setActivityTypes([]);
      });
  }, [canViewOpo]);

  const toggleCheckbox = useCallback(
    (list: string[], value: string, setter: (next: string[]) => void) => {
      setter(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
    },
    [],
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      if (!name.trim() || !registrationNumber.trim() || !address.trim() || !registrationDate) {
        setError("Заполните обязательные поля.");
        return;
      }
      setPending(true);
      try {
        const payload: OPOCreatePayload = {
          name: name.trim(),
          registration_number: registrationNumber.trim(),
          hazard_class: hazardClass,
          address: address.trim(),
          registration_date: registrationDate,
          owner_organization_id: ownerOrganizationId,
          operating_organization_id: operatingOrganizationId,
          hazard_sign_ids: hazardSignIds,
          activity_type_ids: activityTypeIds,
          comment: comment.trim() || null,
        };
        await createOpo(payload);
        router.replace(`/organizations/${organizationId}`);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Не удалось создать ОПО.");
      } finally {
        setPending(false);
      }
    },
    [
      name,
      registrationNumber,
      hazardClass,
      address,
      registrationDate,
      ownerOrganizationId,
      operatingOrganizationId,
      hazardSignIds,
      activityTypeIds,
      comment,
      router,
      organizationId,
    ],
  );

  const renderOrganizationSelects = () => {
    if (organizations.length === 0) {
      return (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="owner_organization_id">Владелец *</Label>
            <p className="text-sm text-muted-foreground" id="owner_organization_id">
              Текущая организация
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="operating_organization_id">Эксплуатирующая организация *</Label>
            <p className="text-sm text-muted-foreground" id="operating_organization_id">
              Текущая организация
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="owner_organization_id">Владелец *</Label>
          <Select value={ownerOrganizationId} onValueChange={setOwnerOrganizationId}>
            <SelectTrigger id="owner_organization_id"><SelectValue /></SelectTrigger>
            <SelectContent>
              {organizations.map((org) => (
                <SelectItem key={org.id} value={org.id}>
                  {organizationName(org)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="operating_organization_id">Эксплуатирующая организация *</Label>
          <Select value={operatingOrganizationId} onValueChange={setOperatingOrganizationId}>
            <SelectTrigger id="operating_organization_id"><SelectValue /></SelectTrigger>
            <SelectContent>
              {organizations.map((org) => (
                <SelectItem key={org.id} value={org.id}>
                  {organizationName(org)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/organizations/${organizationId}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">Новое ОПО</h1>
      </div>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Сведения об объекте</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="name">Наименование *</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  maxLength={255}
                  disabled={pending}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="registration_number">Регистрационный номер *</Label>
                <Input
                  id="registration_number"
                  value={registrationNumber}
                  onChange={(e) => setRegistrationNumber(e.target.value)}
                  required
                  maxLength={100}
                  disabled={pending}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="hazard_class">Класс опасности *</Label>
                <Select value={hazardClass} onValueChange={(v) => setHazardClass(v as HazardClass)}>
                  <SelectTrigger id="hazard_class"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {HAZARD_CLASSES.map((cls) => (
                      <SelectItem key={cls.value} value={cls.value}>
                        {cls.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="address">Адрес *</Label>
                <Input
                  id="address"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  required
                  maxLength={500}
                  disabled={pending}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="registration_date">Дата регистрации *</Label>
                <Input
                  id="registration_date"
                  type="date"
                  value={registrationDate}
                  onChange={(e) => setRegistrationDate(e.target.value)}
                  required
                  disabled={pending}
                />
              </div>
            </div>

            {renderOrganizationSelects()}

            {hazardSigns.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Признаки опасности</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {hazardSigns.map((sign) => (
                    <label key={sign.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={hazardSignIds.includes(sign.id)}
                        onChange={() =>
                          toggleCheckbox(hazardSignIds, sign.id, setHazardSignIds)
                        }
                        disabled={pending}
                      />
                      <span>{sign.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {activityTypes.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Виды деятельности</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {activityTypes.map((activity) => (
                    <label key={activity.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={activityTypeIds.includes(activity.id)}
                        onChange={() =>
                          toggleCheckbox(activityTypeIds, activity.id, setActivityTypeIds)
                        }
                        disabled={pending}
                      />
                      <span>{activity.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="comment">Комментарий</Label>
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
                Создать ОПО
              </Button>
              <Button type="button" variant="outline" asChild>
                <Link href={`/organizations/${organizationId}`}>Отмена</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
