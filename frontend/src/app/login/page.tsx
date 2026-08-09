"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, Suspense, useState } from "react";
import { Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/errors";
import { login } from "@/lib/api/resources";
import { useAuth } from "@/lib/auth";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const next = params.get("next") || "/";

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setPending(true);
      try {
        const result = await login(username, password);
        await refresh();
        if (result.must_change_password) {
          router.replace(`/change-password?next=${encodeURIComponent(next)}`);
        } else {
          router.replace(next);
        }
      } catch (err: unknown) {
        if (err instanceof ApiError && err.status === 423) {
          setError("Учётная запись временно заблокирована. Попробуйте позже.");
        } else if (err instanceof ApiError && err.status === 401) {
          setError("Неверное имя пользователя или пароль.");
        } else {
          setError("Сервер недоступен. Проверьте подключение.");
        }
      } finally {
        setPending(false);
      }
    },
    [username, password, next, refresh, router],
  );

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
            <Building2 className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-xl">Справочник ЭПБ</CardTitle>
          <CardDescription>Войдите в учётную запись</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Имя пользователя</Label>
              <Input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={1}
                disabled={pending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Пароль</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={1}
                disabled={pending}
              />
            </div>
            {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
            <Button type="submit" className="w-full" disabled={pending || !username || !password}>
              {pending ? "Вход…" : "Войти"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
