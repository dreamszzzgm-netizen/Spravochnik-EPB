"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { Loader2, ShieldAlert, Wifi } from "lucide-react";
import { useAuth } from "@/lib/auth";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { state, refresh } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (state.status === "unauthenticated") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [state.status, router, pathname]);

  useEffect(() => {
    if (state.status === "offline") {
      const timer = setInterval(() => refresh(), 5000);
      return () => clearInterval(timer);
    }
  }, [state.status, refresh]);

  if (state.status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (state.status === "forbidden") {
    return (
      <div className="flex h-screen items-center justify-center px-4">
        <div className="text-center space-y-3">
          <ShieldAlert className="mx-auto h-12 w-12 text-destructive" />
          <p className="text-lg font-semibold">Нет доступа</p>
          <p className="text-sm text-muted-foreground">У вашей учётной записи недостаточно прав для этого раздела.</p>
        </div>
      </div>
    );
  }

  if (state.status === "offline") {
    return (
      <div className="flex h-screen items-center justify-center px-4">
        <div className="text-center space-y-3">
          <Wifi className="mx-auto h-12 w-12 text-amber-500" />
          <p className="text-lg font-semibold">Сервер недоступен</p>
          <p className="text-sm text-muted-foreground">Проверьте подключение. Повторная проверка каждые 5 секунд.</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
