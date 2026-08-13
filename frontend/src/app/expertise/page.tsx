import { ShieldCheck } from "lucide-react";

import { PilotEmptyModule } from "@/components/pilot-empty-module";
import { PilotSectionHeader } from "@/components/pilot-section-header";
import { PILOT_UNAVAILABLE } from "@/components/pilot-unavailable-copy";

export default function ExpertisePage() {
  return (
    <div className="space-y-6">
      <PilotSectionHeader
        title="Экспертизы"
        description="Экспертизы промышленной безопасности технических устройств и зданий/сооружений"
      />
      <PilotEmptyModule
        icon={ShieldCheck}
        title="Экспертизы пока недоступны"
        description={PILOT_UNAVAILABLE.expertise}
        actionLabel="Перейти к организациям"
        actionHref="/organizations"
      />
    </div>
  );
}
