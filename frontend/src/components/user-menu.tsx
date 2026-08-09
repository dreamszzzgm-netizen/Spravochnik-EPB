"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LifeBuoy, LogOut, Settings, User } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ApiError } from "@/lib/api/errors";
import { getCurrentUser, logout } from "@/lib/api/resources";
import type { CurrentUserResponse } from "@/lib/api/types";
import { userInitials } from "@/lib/api/view-models";
import { userMenuModel } from "@/lib/api/state-models";

export function UserMenu() {
  const [user, setUser] = useState<CurrentUserResponse | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getCurrentUser({ signal: controller.signal }).then(setUser).catch((error: unknown) => {
      if (!controller.signal.aborted) setUnavailable(!(error instanceof ApiError && error.status === 401));
    });
    return () => controller.abort();
  }, []);

  const { username, secondary } = userMenuModel(user, unavailable);

  async function handleLogout() {
    try { await logout(); } catch { /* An expired session is already logged out locally. */ }
    setUser(null);
    window.location.assign("/");
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild><Button variant="ghost" className="h-9 gap-2 px-2 data-[state=open]:bg-accent"><Avatar className="h-7 w-7"><AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">{user ? userInitials(user.username) : "?"}</AvatarFallback></Avatar><div className="hidden text-left text-sm leading-tight md:flex md:flex-col"><span className="font-medium">{username}</span><span className="text-[11px] text-muted-foreground">{secondary}</span></div></Button></DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel><div className="flex flex-col"><span className="text-sm font-medium">{username}</span><span className="text-xs text-muted-foreground">{secondary}</span></div></DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem asChild><Link href="/settings"><User className="mr-2 h-4 w-4" />Профиль</Link></DropdownMenuItem>
          <DropdownMenuItem asChild><Link href="/settings"><Settings className="mr-2 h-4 w-4" />Настройки</Link></DropdownMenuItem>
          <DropdownMenuItem><LifeBuoy className="mr-2 h-4 w-4" />Поддержка</DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-rose-600 focus:text-rose-600" onSelect={() => void handleLogout()}><LogOut className="mr-2 h-4 w-4" />Выйти</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
