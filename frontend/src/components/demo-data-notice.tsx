"use client";

import { usePathname } from "next/navigation";

export function DemoDataNotice() {
  const pathname = usePathname();
  if (pathname === "/organizations") return null;
  return (
    <div className="mb-4 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-900 dark:text-amber-200" role="status">
      Демо-режим: содержимое этой страницы пока основано на mock-данных и не является production-информацией.
    </div>
  );
}
