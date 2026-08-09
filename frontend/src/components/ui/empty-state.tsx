import Link from "next/link";
import { ArrowLeft, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  actionHref,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  actionHref?: string;
}) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="h-6 w-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-foreground">{title}</h3>
          <p className="mx-auto max-w-sm text-sm text-muted-foreground">{description}</p>
        </div>
        {actionLabel && actionHref && (
          <Button asChild variant="outline" size="sm">
            <Link href={actionHref}>
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              {actionLabel}
            </Link>
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
