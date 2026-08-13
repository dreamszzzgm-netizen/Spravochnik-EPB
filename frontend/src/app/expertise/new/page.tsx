"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth";
import {
  createExpertise,
  listContractItems,
  listContracts,
  listDevices,
  listBuildings,
  listExpertiseTypes,
  type BuildingOption,
  type ContractItemOption,
  type ContractOption,
  type DeviceOption,
  type ExpertiseTypeOption,
} from "@/lib/api/expertises";

export default function NewExpertisePage() {
  const router = useRouter();
  const { state } = useAuth();
  const employeeId = state.status === "authenticated" ? state.user.employee_id : null;

  const [contracts, setContracts] = useState<ContractOption[]>([]);
  const [expertiseTypes, setExpertiseTypes] = useState<ExpertiseTypeOption[]>([]);
  const [devices, setDevices] = useState<DeviceOption[]>([]);
  const [buildings, setBuildings] = useState<BuildingOption[]>([]);
  const [items, setItems] = useState<ContractItemOption[]>([]);

  const [contractId, setContractId] = useState("");
  const [expertiseTypeId, setExpertiseTypeId] = useState("");
  const [selectedItemIds, setSelectedItemIds] = useState<string[]>([]);
  const [subjectKind, setSubjectKind] = useState<"device" | "building" | "">("");
  const [deviceId, setDeviceId] = useState("");
  const [buildingId, setBuildingId] = useState("");
  const [internalNumber, setInternalNumber] = useState("");
  const [comment, setComment] = useState("");

  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      listContracts({ signal: controller.signal }),
      listExpertiseTypes({ signal: controller.signal }),
      listDevices({ signal: controller.signal }),
      listBuildings({ signal: controller.signal }),
    ])
      .then(([c, t, d, b]) => {
        setContracts(c.items);
        setExpertiseTypes(t);
        setDevices(d.items);
        setBuildings(b.items);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof ApiError ? caught.detail : "Не удалось загрузить справочники.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!contractId) {
        setItems([]);
        setSelectedItemIds([]);
        return;
      }
      setSelectedItemIds([]);
      listContractItems(contractId, { signal: controller.signal })
        .then(setItems)
        .catch(() => {});
    });
    return () => controller.abort();
  }, [contractId]);

  const subjectDeviceIds = useMemo(
    () => Array.from(new Set(items.filter((i) => selectedItemIds.includes(i.id)).flatMap((i) => i.technical_device_ids))),
    [items, selectedItemIds],
  );
  const subjectBuildingIds = useMemo(
    () => Array.from(new Set(items.filter((i) => selectedItemIds.includes(i.id)).flatMap((i) => i.building_ids))),
    [items, selectedItemIds],
  );

  const toggleItem = (id: string) => {
    setSelectedItemIds((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id],
    );
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!contractId || !expertiseTypeId || !employeeId || selectedItemIds.length === 0) return;
    const technicalDeviceId = subjectKind === "device" ? deviceId : null;
    const subjectBuildingId = subjectKind === "building" ? buildingId : null;
    if (!technicalDeviceId && !subjectBuildingId) {
      setError("Укажите предмет экспертизы.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const created = await createExpertise({
        contract_id: contractId,
        expertise_type_id: expertiseTypeId,
        responsible_expert_id: employeeId,
        contract_item_ids: selectedItemIds,
        internal_number: internalNumber.trim() || undefined,
        comment: comment.trim() || undefined,
        subject: { technical_device_id: technicalDeviceId, building_id: subjectBuildingId },
      });
      router.push(`/expertise/${created.id}`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Не удалось создать экспертизу.");
    } finally {
      setPending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground">
          <Link href="/expertise">
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            К списку экспертиз
          </Link>
        </Button>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <ShieldCheck className="h-6 w-6" />
          Создать экспертизу
        </h1>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
          {error}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Параметры экспертизы</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-2" onSubmit={submit}>
            <div className="space-y-2">
              <Label htmlFor="contract">Договор *</Label>
              <select
                id="contract"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={contractId}
                onChange={(e) => setContractId(e.target.value)}
                disabled={pending}
              >
                <option value="">Выберите договор</option>
                {contracts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.number}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="expertise_type">Тип экспертизы *</Label>
              <select
                id="expertise_type"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={expertiseTypeId}
                onChange={(e) => setExpertiseTypeId(e.target.value)}
                disabled={pending}
              >
                <option value="">Выберите тип</option>
                {expertiseTypes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2 md:col-span-2">
              <Label>Предметы договора *</Label>
              <div className="flex flex-wrap gap-2">
                {items.length === 0 ? (
                  <p className="text-sm text-muted-foreground">У договора нет предметов.</p>
                ) : (
                  items.map((item) => (
                    <label key={item.id} className="inline-flex items-center gap-1.5 text-sm">
                      <input
                        type="checkbox"
                        checked={selectedItemIds.includes(item.id)}
                        onChange={() => toggleItem(item.id)}
                        disabled={pending}
                      />
                      {item.name}
                    </label>
                  ))
                )}
              </div>
            </div>

            <div className="space-y-2 md:col-span-2">
              <Label>Предмет экспертизы *</Label>
              <div className="flex flex-wrap gap-4">
                <select
                  aria-label="Тип предмета"
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                  value={subjectKind}
                  onChange={(e) => setSubjectKind(e.target.value as "device" | "building" | "")}
                  disabled={pending}
                >
                  <option value="">Выберите тип</option>
                  {subjectDeviceIds.length > 0 && <option value="device">Техническое устройство</option>}
                  {subjectBuildingIds.length > 0 && <option value="building">Здание / сооружение</option>}
                </select>

                {subjectKind === "device" && (
                  <select
                    aria-label="Техническое устройство"
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={deviceId}
                    onChange={(e) => setDeviceId(e.target.value)}
                    disabled={pending}
                  >
                    <option value="">Выберите устройство</option>
                    {subjectDeviceIds.map((id) => (
                      <option key={id} value={id}>
                        {devices.find((d) => d.id === id)?.name ?? id}
                      </option>
                    ))}
                  </select>
                )}

                {subjectKind === "building" && (
                  <select
                    aria-label="Здание / сооружение"
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={buildingId}
                    onChange={(e) => setBuildingId(e.target.value)}
                    disabled={pending}
                  >
                    <option value="">Выберите здание</option>
                    {subjectBuildingIds.map((id) => (
                      <option key={id} value={id}>
                        {buildings.find((b) => b.id === id)?.name ?? id}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="internal_number">Номер экспертизы</Label>
              <Input
                id="internal_number"
                value={internalNumber}
                onChange={(e) => setInternalNumber(e.target.value)}
                maxLength={120}
                disabled={pending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="comment">Комментарий</Label>
              <Input
                id="comment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                disabled={pending}
              />
            </div>

            <div className="md:col-span-2">
              <Button
                type="submit"
                disabled={
                  pending ||
                  !contractId ||
                  !expertiseTypeId ||
                  !employeeId ||
                  selectedItemIds.length === 0
                }
              >
                {pending ? "Создание…" : "Создать экспертизу"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
