"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, Suspense, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/errors";
import { changePassword } from "@/lib/api/resources";
import { useAuth } from "@/lib/auth";

function ChangePasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { state, refresh } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [pending, setPending] = useState(false);

  const next = params.get("next") || "/";

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      if (newPassword.length < 12) {
        setError("Новый пароль должен содержать не менее 12 символов.");
        return;
      }
      if (newPassword !== confirmPassword) {
        setError("Пароли не совпадают.");
        return;
      }
      setPending(true);
      try {
        await changePassword(currentPassword, newPassword);
        setSuccess(true);
        await refresh();
        setTimeout(() => router.replace(next), 1500);
      } catch (err: unknown) {
        if (err instanceof ApiError && err.status === 400) {
          setError(err.detail || "Неверный текущий пароль.");
        } else {
          setError("Не удалось сменить пароль. Попробуйте позже.");
        }
      } finally {
        setPending(false);
      }
    },
    [currentPassword, newPassword, confirmPassword, next, router, refresh],
  );

  if (state.status === "loading") return null;
  if (state.status !== "authenticated") {
    router.replace(`/login?next=${encodeURIComponent("/change-password?next=" + encodeURIComponent(next))}`);
    return null;
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500/10">
            <ShieldCheck className="h-6 w-6 text-amber-600" />
          </div>
          <CardTitle className="text-xl">Смена пароля</CardTitle>
          <CardDescription>Требуется установить новый пароль</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="currentPassword">Текущий пароль</Label>
              <Input id="currentPassword" type="password" autoComplete="current-password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required disabled={pending || success} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="newPassword">Новый пароль</Label>
              <Input id="newPassword" type="password" autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={12} disabled={pending || success} />
              <p className="text-xs text-muted-foreground">Минимум 12 символов</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Подтверждение пароля</Label>
              <Input id="confirmPassword" type="password" autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={12} disabled={pending || success} />
            </div>
            {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
            {success && <p className="text-sm text-emerald-600">Пароль успешно изменён. Перенаправление…</p>}
            <Button type="submit" className="w-full" disabled={pending || success || !currentPassword || !newPassword || !confirmPassword}>
              {pending ? "Смена пароля…" : "Сменить пароль"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function ChangePasswordPage() {
  return (
    <Suspense>
      <ChangePasswordForm />
    </Suspense>
  );
}
