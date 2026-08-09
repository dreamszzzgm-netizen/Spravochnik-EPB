import {
  Activity,
  FileCheck2,
  MessageSquare,
  Plus,
  ShieldX,
  CheckCircle2,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { recentActivity } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  status: ArrowRightIcon,
  create: Plus,
  reject: ShieldX,
  doc: FileCheck2,
  comment: MessageSquare,
  task: CheckCircle2,
};

const TONE: Record<string, string> = {
  status: "bg-entity-expertise-muted text-entity-expertise",
  create: "bg-info-muted text-info",
  reject: "bg-danger-muted text-danger",
  doc: "bg-success-muted text-success",
  comment: "bg-entity-document-muted text-entity-document",
  task: "bg-warning-muted text-warning",
};

function ArrowRightIcon({ className }: { className?: string }) {
  return <Activity className={className} />;
}

function timeAgo(iso: string): string {
  const now = new Date();
  const then = new Date(iso);
  const diffH = Math.round((now.getTime() - then.getTime()) / 3_600_000);
  if (diffH < 1) return "только что";
  if (diffH < 24) return `${diffH} ч назад`;
  const diffD = Math.round(diffH / 24);
  return `${diffD} ${diffD === 1 ? "день" : diffD < 5 ? "дня" : "дней"} назад`;
}

export function RecentActivity() {
  return (
    <Card className="h-full">
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-entity-expertise-muted text-entity-expertise">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <CardTitle className="text-base">Последние события</CardTitle>
            <p className="text-xs text-muted-foreground">Лента изменений по системе</p>
          </div>
        </div>
      </CardHeader>
      <Separator />
      <CardContent className="p-0">
        <ul className="divide-y divide-border">
          {recentActivity.map((a) => {
            const Icon = ICONS[a.type] ?? Activity;
            return (
              <li key={a.id} className="flex gap-3 px-4 py-3">
                <div
                  className={cn(
                    "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                    TONE[a.type]
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm leading-snug text-foreground">{a.text}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{timeAgo(a.at)}</p>
                </div>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
