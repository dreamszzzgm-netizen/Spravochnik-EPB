"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { CalendarClock } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { DeadlineChip } from "@/components/dashboard/deadline-chip";
import { expiringSoon } from "@/lib/mock-data";

const KIND_LABEL: Record<string, string> = {
  expertise: "Экспертиза",
  contract: "Договор",
  device: "Техническое устройство",
};

type KindFilter = "all" | "expertise" | "contract" | "device";

const FILTERS: { value: KindFilter; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "expertise", label: "Экспертизы" },
  { value: "contract", label: "Договоры" },
  { value: "device", label: "ТУ" },
];

export function ExpiringSoon() {
  const [filter, setFilter] = useState<KindFilter>("all");

  const filtered = useMemo(() => {
    const items =
      filter === "all"
        ? expiringSoon
        : expiringSoon.filter((e) => e.kind === filter);
    return [...items].sort((a, b) => a.date.getTime() - b.date.getTime());
  }, [filter]);

  return (
    <Card className="h-full">
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
            <CalendarClock className="h-4 w-4" />
          </div>
          <div>
            <CardTitle className="text-base">Ближайшие сроки</CardTitle>
            <p className="text-xs text-muted-foreground">На 14 дней вперёд</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/calendar">Календарь</Link>
        </Button>
      </CardHeader>
      <div className="px-4 pb-3">
        <ToggleGroup
          type="single"
          value={filter}
          onValueChange={(v) => v && setFilter(v as KindFilter)}
          variant="outline"
          size="sm"
          className="flex-wrap justify-start gap-1"
        >
          {FILTERS.map((f) => (
            <ToggleGroupItem key={f.value} value={f.value} aria-label={f.label}>
              {f.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <Separator />
      <CardContent className="p-0">
        {filtered.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            Нет событий в выбранной категории
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {filtered.map((e) => (
              <li
                key={e.id}
                className={
                  e.severity === "urgent"
                    ? "border-l-2 border-l-deadline-overdue"
                    : e.severity === "warning"
                      ? "border-l-2 border-l-deadline-soon"
                      : "border-l-2 border-l-deadline-ok"
                }
              >
                <Link
                  href={e.kind === "expertise" ? `/expertise/${e.id}` : "/calendar"}
                  className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-muted/40"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <p className="line-clamp-1 text-sm font-medium text-foreground">
                        {e.title}
                      </p>
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide">
                        {KIND_LABEL[e.kind]}
                      </span>
                      <span className="font-mono">{e.contractNumber}</span>
                    </div>
                  </div>
                  <DeadlineChip date={e.date} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
