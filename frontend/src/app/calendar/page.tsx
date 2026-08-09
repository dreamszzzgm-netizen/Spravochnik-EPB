import { CalendarDays } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";

export default function CalendarPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Календарь</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Сроки договоров, задач, экспертиз и контрольные даты
        </p>
      </div>
      <EmptyState
        icon={CalendarDays}
        title="Календарь появится в ближайших релизах"
        description="События по договорам, задачам, экспертизам и техническим устройствам с расчётом по производственному календарю РФ."
      />
    </div>
  );
}
