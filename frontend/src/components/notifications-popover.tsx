"use client";

import { Bell, ListTodo, Calendar, MessageSquare, AlertTriangle, ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { notifications, type NotificationKind } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

const iconByKind: Record<NotificationKind, React.ComponentType<{ className?: string }>> = {
  task: ListTodo,
  deadline: AlertTriangle,
  overdue: AlertTriangle,
  status: ArrowRight,
  mention: MessageSquare,
  control: Calendar,
};

const toneByKind: Record<NotificationKind, string> = {
  task: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  deadline: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  overdue: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
  status: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
  mention: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
  control: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
};

function timeAgo(iso: string): string {
  const now = new Date();
  const then = new Date(iso);
  const diffMin = Math.round((now.getTime() - then.getTime()) / 60000);
  if (diffMin < 1) return "только что";
  if (diffMin < 60) return `${diffMin} мин назад`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `${diffH} ч назад`;
  const diffD = Math.round(diffH / 24);
  if (diffD < 7) return `${diffD} дн назад`;
  return then.toLocaleDateString("ru-RU");
}

export function NotificationsPopover() {
  const unread = notifications.filter((n) => !n.read).length;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative h-9 w-9"
          aria-label="Уведомления"
        >
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span className="absolute right-1.5 top-1.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white">
              {unread}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[380px] p-0">
        <div className="flex items-center justify-between px-4 py-3">
          <div>
            <h4 className="text-sm font-semibold">Уведомления</h4>
            <p className="text-xs text-muted-foreground">
              {unread > 0 ? `${unread} новых` : "Все прочитано"}
            </p>
          </div>
          <Button variant="ghost" size="sm" className="h-7 text-xs">
            Прочитать все
          </Button>
        </div>
        <Separator />
        <ScrollArea className="h-[420px]">
          <ul className="divide-y divide-border">
            {notifications.map((n) => {
              const Icon = iconByKind[n.kind];
              return (
                <li
                  key={n.id}
                  className={cn(
                    "flex gap-3 px-4 py-3 transition-colors hover:bg-muted/50",
                    !n.read && "bg-accent/30"
                  )}
                >
                  <div
                    className={cn(
                      "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                      toneByKind[n.kind]
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm leading-snug">{n.title}</p>
                      {!n.read && (
                        <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      )}
                    </div>
                    {n.description && (
                      <p className="mt-0.5 text-xs text-muted-foreground">{n.description}</p>
                    )}
                    <p className="mt-1 text-[11px] text-muted-foreground">{timeAgo(n.at)}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </ScrollArea>
        <Separator />
        <div className="p-2">
          <Button variant="ghost" size="sm" className="w-full justify-center">
            Открыть все уведомления
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
