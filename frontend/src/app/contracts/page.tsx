import Link from "next/link";
import { ChevronRight, FileText, Plus, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { contracts, formatMoney } from "@/lib/mock-data";

export default function ContractsPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Договоры</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Договоры, предметы и дополнительные соглашения
          </p>
        </div>
        <Button size="sm">
          <Plus className="mr-1.5 h-4 w-4" />
          Новый договор
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative max-w-md flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Поиск по номеру, заказчику…" className="pl-9" />
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <ul className="divide-y divide-border">
            {contracts.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/contracts/${c.id}`}
                  className="flex items-center gap-4 px-4 py-4 transition-colors hover:bg-muted/40"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-mono text-sm font-medium text-foreground">
                        {c.number}
                      </p>
                      <StatusBadge status={c.status} kind="contract" />
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {c.organizationName} · {c.responsible} · {c.expertiseCount} экспертиз
                    </p>
                  </div>
                  <div className="hidden text-right text-sm sm:block">
                    <p className="font-medium tabular-nums text-foreground">
                      {formatMoney(c.amount)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      до {c.endDate}
                    </p>
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
