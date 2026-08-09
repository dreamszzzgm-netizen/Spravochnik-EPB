import Link from "next/link";
import { ArrowRight, type LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function KpiCard({
  label,
  value,
  hint,
  delta,
  icon: Icon,
  tone = "default",
  href,
  footerLabel,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  delta?: { value: string; trend: "up" | "down" | "flat" };
  icon: LucideIcon;
  tone?: "default" | "warning" | "danger" | "success";
  href?: string;
  footerLabel?: string;
}) {
  const toneClass = {
    default: "bg-primary/10 text-primary",
    warning: "bg-warning-muted text-warning",
    danger: "bg-danger-muted text-danger",
    success: "bg-success-muted text-success",
  }[tone];

  const inner = (
    <Card
      className={cn(
        "h-full border-border/70 transition-colors",
        href && "hover:border-primary/40 hover:bg-accent/30"
      )}
    >
      <CardContent className="flex h-full flex-col justify-between gap-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {label}
            </p>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
              {value}
            </p>
          </div>
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", toneClass)}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
        <div className="flex items-end justify-between gap-2">
          <div className="min-w-0 text-xs text-muted-foreground">
            {hint}
            {delta && (
              <span
                className={cn(
                  "ml-1.5 inline-flex items-center gap-0.5 font-medium",
                  delta.trend === "up" && "text-success",
                  delta.trend === "down" && "text-danger",
                  delta.trend === "flat" && "text-muted-foreground"
                )}
              >
                {delta.value}
              </span>
            )}
          </div>
          {href && footerLabel && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-primary">
              {footerLabel}
              <ArrowRight className="h-3.5 w-3.5" />
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );

  return href ? (
    <Link href={href} className="block h-full">
      {inner}
    </Link>
  ) : (
    inner
  );
}
