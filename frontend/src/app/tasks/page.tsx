import { Plus, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { PriorityBadge } from "@/components/dashboard/priority-badge";
import { DeadlineChip } from "@/components/dashboard/deadline-chip";
import { myTasks } from "@/lib/mock-data";

export default function TasksPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Задачи</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Мои задачи и задачи сотрудников
          </p>
        </div>
        <Button size="sm">
          <Plus className="mr-1.5 h-4 w-4" />
          Новая задача
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative max-w-md flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Поиск по названию, описанию…" className="pl-9" />
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <ul className="divide-y divide-border">
            {myTasks.map((t) => (
              <li
                key={t.id}
                className={
                  t.overdue
                    ? "border-l-2 border-l-deadline-overdue"
                    : "border-l-2 border-l-transparent"
                }
              >
                <div className="flex items-start gap-4 px-4 py-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground">{t.title}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                      <span className="font-mono">{t.expertiseNumber}</span>
                      <span>·</span>
                      <DeadlineChip date={parseDate(t.dueDate)} showIcon={false} />
                      <PriorityBadge priority={t.priority} />
                    </div>
                  </div>
                  <StatusBadge status={t.status} kind="task" />
                </div>
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
