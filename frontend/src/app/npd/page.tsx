import { BookOpen } from "lucide-react";

import { PilotEmptyModule } from "@/components/pilot-empty-module";
import { PilotSectionHeader } from "@/components/pilot-section-header";
import { PILOT_UNAVAILABLE } from "@/components/pilot-unavailable-copy";

export default function NpdPage() {
  return (
    <div className="space-y-6">
      <PilotSectionHeader
        title="НПД"
        description="Нормативно-техническая документация: ФНП, ГОСТ, СП, РД и другие документы"
      />
      <PilotEmptyModule
        icon={BookOpen}
        title="НПД пока не загружены"
        description={PILOT_UNAVAILABLE.npd}
      />
    </div>
  );
}
