import Link from "next/link";
import { ChevronRight, Plus, Search, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { DeadlineChip } from "@/components/dashboard/deadline-chip";
import { expertiseList } from "@/lib/mock-data";

export default function ExpertisePage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Экспертизы</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Экспертизы промышленной безопасности технических устройств и зданий/сооружений
          </p>
        </div>
        <Button size="sm">
          <Plus className="mr-1.5 h-4 w-4" />
          Новая экспертиза
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative max-w-md flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Поиск по номеру, предмету экспертизы…" className="pl-9" />
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <ul className="divide-y divide-border">
            {expertiseList.map((e) => (
              <li key={e.id}>
                <Link
                  href={`/expertise/${e.id}`}
                  className="flex items-center gap-4 px-4 py-4 transition-colors hover:bg-muted/40"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                    <ShieldCheck className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-mono text-sm font-medium text-foreground">
                        {e.number}
                      </p>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                        {e.subjectType}
                      </span>
                      <StatusBadge status={e.status} kind="expertise" />
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {e.subjectName} · {e.organizationName} · {e.contractNumber} · {e.responsible}
                    </p>
                  </div>
                  <div className="hidden text-right text-xs sm:block">
                    <DeadlineChip date={parseDate(e.nextControl)} />
                    <p className="mt-1 text-muted-foreground">контрольная дата</p>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function parseDate(s: string): Date {
  const [d, m, y] = s.split(".");
  return new Date(Number(y), Number(m) - 1, Number(d));
}
