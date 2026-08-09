"use client";

import { AlertTriangle, CalendarClock, Clock } from "lucide-react";

import { cn } from "@/lib/utils";

export function DeadlineChip({
  date,
  className,
  showIcon = true,
}: {
  date: Date;
  className?: string;
  showIcon?: boolean;
}) {
  const fallback = formatDate(date);

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffDays = Math.round((target.getTime() - startOfToday.getTime()) / 86_400_000);

  const overdue = diffDays < 0;
  const soon = diffDays >= 0 && diffDays <= 5;
  const ok = diffDays > 5;

  const Icon = overdue ? AlertTriangle : soon ? Clock : CalendarClock;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-medium",
        overdue && "text-deadline-overdue",
        soon && "text-deadline-soon",
        ok && "text-deadline-ok",
        className,
      )}
    >
      {showIcon && <Icon className="h-3.5 w-3.5" />}
      {overdue && diffDays === -1 && "Вчера"}
      {overdue && diffDays < -1 &&
        `Просрочка: ${Math.abs(diffDays)} ${plural(Math.abs(diffDays), ["день", "дня", "дней"])}`}
      {!overdue && diffDays === 0 && "Сегодня"}
      {!overdue && diffDays === 1 && "Завтра"}
      {!overdue && diffDays > 1 && diffDays <= 14 &&
        `Через ${diffDays} ${plural(diffDays, ["день", "дня", "дней"])}`}
      {!overdue && diffDays > 14 && fallback}
    </span>
  );
}

function plural(n: number, forms: [string, string, string]) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1];
  return forms[2];
}

function formatDate(d: Date) {
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}
