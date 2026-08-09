import Link from "next/link";
import { ArrowLeft, Building2, Calendar, FileText, Shield, User } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { DeadlineChip } from "@/components/dashboard/deadline-chip";
import { expertiseDetail } from "@/lib/mock-data";

export function ExpertiseHeader() {
  const e = expertiseDetail;
  return (
    <div className="space-y-4">
      <div>
        <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground">
          <Link href="/expertise">
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            К списку экспертиз
          </Link>
        </Button>
      </div>

      <Card className="overflow-hidden">
        <div className="flex flex-col gap-5 p-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                {e.subject.type}
              </span>
              <StatusBadge status={e.status} kind="expertise" />
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
              {e.subject.name}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
              <span className="font-mono">{e.number}</span>
              <span>·</span>
              <Link
                href={`/contracts/${e.contractId}`}
                className="inline-flex items-center gap-1 hover:text-foreground"
              >
                <FileText className="h-3.5 w-3.5" />
                {e.contractNumber}
              </Link>
              <span>·</span>
              <span className="inline-flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5" />
                {e.organization.name}
              </span>
              <span>·</span>
              <span className="inline-flex items-center gap-1">
                <User className="h-3.5 w-3.5" />
                {e.responsibleExpert.name}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm">
              Сформировать пакет в РТН
            </Button>
            <Button size="sm">Подготовить заключение</Button>
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 border-t border-border bg-muted/30 px-5 py-4 text-sm sm:grid-cols-4">
          <Field label="Тип экспертизы" value={e.type} />
          <Field
            label="Дата создания"
            value={e.createdAt}
            icon={<Calendar className="h-3.5 w-3.5 text-muted-foreground" />}
          />
          <Field
            label="Направлено в РТН"
            value={e.submittedToRtnAt}
            icon={<Shield className="h-3.5 w-3.5 text-muted-foreground" />}
          />
          <Field
            label="Контрольная дата"
            value={
              <DeadlineChip date={addDays(2)} />
            }
          />
        </dl>
      </Card>
    </div>
  );
}

function Field({
  label,
  value,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 flex items-center gap-1.5 truncate text-sm text-foreground">{icon}{value}</dd>
    </div>
  );
}

function addDays(n: number): Date {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d;
}
