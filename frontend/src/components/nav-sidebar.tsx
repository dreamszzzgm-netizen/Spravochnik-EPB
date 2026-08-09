"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { mainNav, settingsNav } from "@/components/nav-config";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { BackendStatus } from "@/components/backend-status";

export function NavSidebar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <aside className="hidden w-64 shrink-0 border-r border-sidebar-border bg-sidebar md:flex md:flex-col">
      <div className="flex h-16 items-center px-5">
        <Link href="/" className="flex items-center">
          <Logo />
        </Link>
      </div>
      <Separator />

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        <p className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Основное
        </p>
        <ul className="space-y-0.5">
          {mainNav.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                    active
                      ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                      : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      active
                        ? "text-sidebar-primary"
                        : "text-muted-foreground group-hover:text-sidebar-foreground"
                    )}
                  />
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.href === "/tasks" && (
                    <Badge
                      variant="secondary"
                      className="h-5 min-w-[20px] justify-center rounded-full px-1.5 text-[10px] font-semibold"
                    >
                      7
                    </Badge>
                  )}
                  {item.href === "/expertise" && (
                    <Badge
                      variant="secondary"
                      className="h-5 min-w-[20px] justify-center rounded-full px-1.5 text-[10px] font-semibold"
                    >
                      4
                    </Badge>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>

        <p className="mt-6 px-2 pb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Система
        </p>
        <ul className="space-y-0.5">
          {settingsNav.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                    active
                      ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                      : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      active
                        ? "text-sidebar-primary"
                        : "text-muted-foreground group-hover:text-sidebar-foreground"
                    )}
                  />
                  <span className="flex-1 truncate">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <Separator />
      <div className="px-5 py-3">
        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
          <BackendStatus />
          <span className="font-mono">v0.1.0</span>
        </div>
      </div>
    </aside>
  );
}
