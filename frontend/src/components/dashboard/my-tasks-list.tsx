"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Check, ListTodo, Square } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { DeadlineChip } from "@/components/dashboard/deadline-chip";
import { PriorityBadge } from "@/components/dashboard/priority-badge";
import { myTasks } from "@/lib/mock-data";

function parseDate(s: string): Date {
  const [d, m, y] = s.split(".");
  return new Date(Number(y), Number(m) - 1, Number(d));
}

export function MyTasksList() {
  const [done, setDone] = useState<Set<string>>(() => new Set());

  const sorted = useMemo(
    () =>
      [...myTasks].sort((a, b) => {
        if (a.overdue !== b.overdue) return a.overdue ? -1 : 1;
        return a.priority.length - b.priority.length;
      }),
    [],
  );

  const completedToday = done.size;
  const overdue = sorted.filter((t) => t.overdue).length;

  const toggle = (id: string) => {
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <Card className="h-full">
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <ListTodo className="h-4 w-4" />
          </div>
          <div>
            <CardTitle className="text-base">Мои задачи</CardTitle>
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground tabular-nums">
                {completedToday}
              </span>{" "}
              из <span className="tabular-nums">{sorted.length}</span> выполнено сегодня
              {overdue > 0 && (
                <>
                  {" · "}
                  <span className="text-deadline-overdue">{overdue} просрочено</span>
                </>
              )}
            </p>
          </div>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/tasks">Все задачи</Link>
        </Button>
      </CardHeader>
      <Separator />
      <CardContent className="p-0">
        <ul className="divide-y divide-border">
          {sorted.map((t) => {
            const isDone = done.has(t.id);
            return (
              <li
                key={t.id}
                className={
                  isDone
                    ? "border-l-2 border-l-transparent opacity-60"
                    : t.overdue
                      ? "border-l-2 border-l-deadline-overdue"
                      : "border-l-2 border-l-transparent"
                }
              >
                <div className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-muted/40">
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={isDone}
                    aria-label={isDone ? "Отменить выполнение" : "Отметить выполненной"}
                    onClick={() => toggle(t.id)}
                    className="task-checkbox-hit-area -m-3 mt-[-10px] inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  >
                    <span className="task-checkbox-visual inline-flex h-5 w-5 items-center justify-center rounded border border-border transition-colors hover:bg-muted">
                      {isDone ? (
                        <Check className="h-3.5 w-3.5" />
                      ) : (
                        <Square className="h-3.5 w-3.5 opacity-0" aria-hidden />
                      )}
                    </span>
                  </button>
                  <Link
                    href={`/tasks/${t.id}`}
                    className="min-w-0 flex-1"
                  >
                    <div className="flex items-start gap-2">
                      <p
                        className={
                          isDone
                            ? "line-clamp-1 text-sm font-medium text-muted-foreground line-through decoration-muted-foreground/50"
                            : "line-clamp-1 text-sm font-medium text-foreground"
                        }
                      >
                        {t.title}
                      </p>
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                      <span className="font-mono">{t.expertiseNumber}</span>
                      <span>·</span>
                      <DeadlineChip date={parseDate(t.dueDate)} showIcon={false} />
                      <PriorityBadge priority={t.priority} />
                    </div>
                  </Link>
                </div>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
