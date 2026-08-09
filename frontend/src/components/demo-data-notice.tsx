"use client";

import { usePathname } from "next/navigation";

export function DemoDataNotice() {
  const pathname = usePathname();
  if (pathname === "/organizations") return null;
  return (
    <div className="mb-4 rounded-md border border-warning/30 bg-warning-muted px-3 py-2 text-xs text-warning" role="status">
      Демо-режим: содержимое этой страницы пока основано на mock-данных и не является production-информацией.
    </div>
  );
}
