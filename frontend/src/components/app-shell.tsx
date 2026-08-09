"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { NavSidebar } from "@/components/nav-sidebar";
import { TopBar } from "@/components/top-bar";
import { DemoDataNotice } from "@/components/demo-data-notice";
import { AuthGate } from "@/components/auth-gate";

const PUBLIC = new Set(["/login", "/change-password"]);

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (PUBLIC.has(pathname)) {
    return <>{children}</>;
  }

  return (
    <AuthGate>
      <div className="flex h-screen w-full overflow-hidden bg-background">
        <NavSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
              <DemoDataNotice />
              {children}
            </div>
          </main>
        </div>
      </div>
    </AuthGate>
  );
}
