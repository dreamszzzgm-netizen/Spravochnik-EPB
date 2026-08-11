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
import { ApiError } from "@/lib/api/errors";
import { createTechnicalDevice, getOpoList } from "@/lib/api/resources";
import type { OPOResponse, TechnicalDeviceCreatePayload, TechnicalDeviceType } from "@/lib/api/types";

const DEVICE_TYPES: { value: TechnicalDeviceType; label: string }[] = [
  { value: "pressure_vessel", label: "Сосуд под давлением" },
  { value: "pipeline", label: "Трубопровод" },
  { value: "lifting_mechanism", label: "Подъёмное сооружение" },
  { value: "other", label: "Другое" },
];

const NO_OPO_ID = "___no_opo___";

export default function NewTechnicalDevicePage() {
  const params = useParams();
  const router = useRouter();
  const organizationId = params.id as string;

  const [name, setName] = useState("");
  const [deviceType, setDeviceType] = useState<TechnicalDeviceType>("other");
  const [serialNumber, setSerialNumber] = useState("");
  const [opoId, setOpoId] = useState(NO_OPO_ID);

  const [opos, setOpos] = useState<OPOResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    getOpoList({ organization_id: organizationId, page: 1, page_size: 100 })
      .then((data) => setOpos(data.items))
      .catch((e) => setLoadError(e instanceof ApiError ? e.detail : "Ошибка загрузки"))
      .finally(() => setLoading(false));
  }, [organizationId]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      if (!name.trim()) {
        setError("Наименование обязательно.");
        return;
      }
      setPending(true);
      try {
        const payload: TechnicalDeviceCreatePayload = {
          name: name.trim(),
          device_type: deviceType,
          serial_number: serialNumber.trim() || null,
          opo_id: opoId === NO_OPO_ID ? null : opoId,
          organization_id: organizationId,
        };
        await createTechnicalDevice(payload);
        router.replace(`/organizations/${organizationId}`);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Не удалось создать техническое устройство.");
      } finally {
        setPending(false);
      }
    },
    [name, deviceType, serialNumber, opoId, organizationId, router],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/organizations/${organizationId}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">Новое техническое устройство</h1>
      </div>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Сведения об устройстве</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {loading ? (
              <p className="text-sm text-muted-foreground">Загрузка данных...</p>
            ) : loadError ? (
              <p className="text-sm text-destructive" role="alert">
                {loadError}
              </p>
            ) : (
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
                  <Label htmlFor="device_type">Тип устройства *</Label>
                  <Select value={deviceType} onValueChange={(v) => setDeviceType(v as TechnicalDeviceType)}>
                    <SelectTrigger id="device_type"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {DEVICE_TYPES.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="serial_number">Заводской/серийный номер</Label>
                  <Input
                    id="serial_number"
                    value={serialNumber}
                    onChange={(e) => setSerialNumber(e.target.value)}
                    maxLength={128}
                    disabled={pending}
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="opo_id">ОПО</Label>
                  <Select value={opoId} onValueChange={setOpoId}>
                    <SelectTrigger id="opo_id"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NO_OPO_ID}>Без ОПО</SelectItem>
                      {opos.map((opo) => (
                        <SelectItem key={opo.id} value={opo.id}>
                          {opo.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={pending || loading || !!loadError}>
                Создать устройство
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
