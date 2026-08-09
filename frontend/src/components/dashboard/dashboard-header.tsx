"use client";

import Link from "next/link";
import { useState } from "react";
import { Plus, FilePlus, ShieldPlus, ListTodo } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { currentUser } from "@/lib/mock-data";

function greetingForHour(h: number): string {
  if (h < 6) return "Доброй ночи";
  if (h < 12) return "Доброе утро";
  if (h < 18) return "Добрый день";
  return "Добрый вечер";
}

function formatToday(d: Date): string {
  return d.toLocaleDateString("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function DashboardHeader() {
  const firstName = currentUser.name.split(" ")[1] ?? currentUser.name;
  const [now] = useState<Date>(() => new Date());

  const greeting = now ? greetingForHour(now.getHours()) : "Здравствуйте";
  const todayLabel = now
    ? formatToday(now)
    : new Date(2026, 0, 1).toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          {greeting}, {firstName}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground capitalize" suppressHydrationWarning>
          {todayLabel}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" asChild>
          <Link href="/tasks?new=1">
            <ListTodo className="mr-1.5 h-4 w-4" />
            Новая задача
          </Link>
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm">
              <Plus className="mr-1.5 h-4 w-4" />
              Создать
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>Быстрое создание</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/contracts?new=1">
                <FilePlus className="mr-2 h-4 w-4" />
                Договор
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/expertise?new=1">
                <ShieldPlus className="mr-2 h-4 w-4" />
                Экспертизу
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/organizations?new=1">
                <Plus className="mr-2 h-4 w-4" />
                Организацию
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
