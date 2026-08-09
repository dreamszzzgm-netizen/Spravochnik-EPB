"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api/resources";
import { backendStatusLabel, type BackendState } from "@/lib/api/state-models";

export function BackendStatus() {
  const [state, setState] = useState<BackendState>("checking");

  useEffect(() => {
    const controller = new AbortController();
    getHealth({ signal: controller.signal }).then(() => setState("online")).catch(() => {
      if (!controller.signal.aborted) setState("offline");
    });
    return () => controller.abort();
  }, []);

  const label = backendStatusLabel(state);
  return (
    <div className="hidden items-center gap-1.5 text-xs text-muted-foreground lg:flex" title={label}>
      <span className={`h-2 w-2 rounded-full ${state === "online" ? "bg-success" : state === "offline" ? "bg-danger" : "bg-warning animate-pulse"}`} />
      {label}
    </div>
  );
}
