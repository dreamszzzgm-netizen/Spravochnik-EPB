import * as React from "react";

import { NavSidebar } from "@/components/nav-sidebar";
import { TopBar } from "@/components/top-bar";
import { DemoDataNotice } from "@/components/demo-data-notice";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
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
  );
}
