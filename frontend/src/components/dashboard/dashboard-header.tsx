"use client";

import Link from "next/link";
import { useState } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

function greetingForHour(hour: number): string {
  if (hour < 6) return "Доброй ночи";
  if (hour < 12) return "Доброе утро";
  if (hour < 18) return "Добрый день";
  return "Добрый вечер";
}

function formatToday(date: Date): string {
  return date.toLocaleDateString("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function DashboardHeader() {
  const { state } = useAuth();
  const [now] = useState<Date>(() => new Date());
  const username = state.status === "authenticated" ? state.user.username : "пользователь";

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          {greetingForHour(now.getHours())}, {username}
        </h1>
        <p className="mt-1 text-sm capitalize text-muted-foreground" suppressHydrationWarning>
          {formatToday(now)}
        </p>
      </div>

      <Button size="sm" asChild>
        <Link href="/organizations/new">
          <Plus className="mr-1.5 h-4 w-4" />
          Новая организация
        </Link>
      </Button>
    </div>
  );
}
