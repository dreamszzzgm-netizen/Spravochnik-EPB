"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { mainNav, settingsNav } from "@/components/nav-config";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";

export function MobileNav() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <nav className="flex-1 overflow-y-auto px-3 py-4">
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
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/60"
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    active ? "text-sidebar-primary" : "text-muted-foreground"
                  )}
                />
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
      <Separator className="my-4" />
      <p className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
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
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/60"
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    active ? "text-sidebar-primary" : "text-muted-foreground"
                  )}
                />
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
