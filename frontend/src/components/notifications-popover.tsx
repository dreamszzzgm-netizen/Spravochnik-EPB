"use client";

import { Bell } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";

export function NotificationsPopover() {
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
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(380px,calc(100vw-2rem))] p-0">
        <div className="px-4 py-3">
          <h4 className="text-sm font-semibold">Уведомления</h4>
          <p className="text-xs text-muted-foreground">Новых уведомлений нет</p>
        </div>
        <Separator />
        <div className="px-4 py-8 text-center">
          <p className="text-sm font-medium text-foreground">Список уведомлений пуст</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Серверный источник уведомлений будет подключён отдельным этапом.
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
