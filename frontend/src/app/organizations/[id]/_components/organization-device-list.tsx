"use client";

import { useEffect, useState } from "react";
import { Plus, Loader2, Wrench } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import { getTechnicalDevices } from "@/lib/api/resources";
import type { TechnicalDeviceResponse } from "@/lib/api/types";
import { technicalDeviceTypeLabel } from "@/lib/api/view-models";
import { useCan } from "@/lib/auth";

export function OrganizationDeviceList({ organizationId }: { organizationId: string }) {
  const [items, setItems] = useState<TechnicalDeviceResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const canCreate = useCan("technical_devices.create");

  useEffect(() => {
    const controller = new AbortController();
    getTechnicalDevices({
      organization_id: organizationId,
      page: 1,
      page_size: 100,
      signal: controller.signal,
    })
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e instanceof ApiError ? e.detail : "Ошибка загрузки");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [organizationId]);

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          {error}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Технические устройства</CardTitle>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{total}</span>
          {canCreate && (
            <Button variant="outline" size="sm" asChild>
              <Link href={`/organizations/${organizationId}/devices/new`}>
                <Plus className="mr-1 h-4 w-4" />
                Добавить
              </Link>
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            Технические устройства для этой организации пока не добавлены.
          </p>
        ) : (
          <ul className="divide-y">
            {items.map((device) => (
              <li key={device.id} className="flex items-start gap-3 py-3">
                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <Wrench className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{device.name}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {technicalDeviceTypeLabel(device.device_type)}
                    {device.serial_number ? ` · ${device.serial_number}` : ""}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground">
                  {device.opo_id ? "ОПО привязано" : "Без ОПО"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
