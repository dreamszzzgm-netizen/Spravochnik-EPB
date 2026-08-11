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
import { createBuilding, getOpoList } from "@/lib/api/resources";
import type { BuildingCreatePayload, BuildingType, OPOResponse } from "@/lib/api/types";
import { useCan } from "@/lib/auth";

const BUILDING_TYPES: { value: BuildingType; label: string }[] = [
  { value: "industrial", label: "Производственное" },
  { value: "warehouse", label: "Складское" },
  { value: "administrative", label: "Административное" },
  { value: "other", label: "Другое" },
];

const NO_OPO_ID = "___no_opo___";

export default function NewBuildingPage() {
  const params = useParams();
  const router = useRouter();
  const organizationId = params.id as string;
  const canViewOpo = useCan("opo.view");

  const [name, setName] = useState("");
  const [buildingType, setBuildingType] = useState<BuildingType>("other");
  const [opoId, setOpoId] = useState(NO_OPO_ID);

  const [opos, setOpos] = useState<OPOResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!canViewOpo) return;

    getOpoList({ organization_id: organizationId, page: 1, page_size: 100 })
      .then((data) => setOpos(data.items))
      .catch(() => setOpos([]));
  }, [canViewOpo, organizationId]);

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
        const payload: BuildingCreatePayload = {
          name: name.trim(),
          building_type: buildingType,
          opo_id: opoId === NO_OPO_ID ? null : opoId,
          organization_id: organizationId,
        };
        await createBuilding(payload);
        router.replace(`/organizations/${organizationId}`);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Не удалось создать здание или сооружение.");
      } finally {
        setPending(false);
      }
    },
    [name, buildingType, opoId, organizationId, router],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/organizations/${organizationId}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">Новое здание или сооружение</h1>
      </div>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Сведения о здании</CardTitle>
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
                <Label htmlFor="building_type">Тип *</Label>
                <Select value={buildingType} onValueChange={(v) => setBuildingType(v as BuildingType)}>
                  <SelectTrigger id="building_type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {BUILDING_TYPES.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
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

            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={pending}>
                Создать здание
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
