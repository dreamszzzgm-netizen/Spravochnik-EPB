import { FileText } from "lucide-react";

import { PilotEmptyModule } from "@/components/pilot-empty-module";
import { PilotSectionHeader } from "@/components/pilot-section-header";
import { PILOT_UNAVAILABLE } from "@/components/pilot-unavailable-copy";

export default function ContractsPage() {
  return (
    <div className="space-y-6">
      <PilotSectionHeader
        title="Договоры"
        description="Договоры, предметы и дополнительные соглашения"
      />
      <PilotEmptyModule
        icon={FileText}
        title="Договоры пока не отображаются"
        description={PILOT_UNAVAILABLE.contracts}
        actionLabel="Перейти к организациям"
        actionHref="/organizations"
      />
    </div>
  );
}
