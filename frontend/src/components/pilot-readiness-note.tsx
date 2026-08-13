import { Info } from "lucide-react";

export function PilotReadinessNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
      <Info className="mt-0.5 h-4 w-4 shrink-0" />
      <p>{children}</p>
    </div>
  );
}
