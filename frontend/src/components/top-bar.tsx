"use client";

import Link from "next/link";
import { Menu } from "lucide-react";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { CommandSearch } from "@/components/command-search";
import { NotificationsPopover } from "@/components/notifications-popover";
import { UserMenu } from "@/components/user-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { MobileNav } from "@/components/mobile-nav";
import { BackendStatus } from "@/components/backend-status";

export function TopBar() {
  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur-md sm:px-6">
      <Sheet>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 md:hidden"
            aria-label="Меню"
          >
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 p-0">
          <SheetHeader className="border-b border-border px-5 py-4">
            <SheetTitle>
              <Link href="/" className="flex items-center">
                <Logo />
              </Link>
            </SheetTitle>
          </SheetHeader>
          <MobileNav />
        </SheetContent>
      </Sheet>

      <div className="flex flex-1 items-center justify-center md:justify-start">
        <CommandSearch />
      </div>

      <div className="flex items-center gap-1">
        <BackendStatus />
        <ThemeToggle />
        <NotificationsPopover />
        <UserMenu />
      </div>
    </header>
  );
}
