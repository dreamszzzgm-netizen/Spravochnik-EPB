import { ShieldCheck } from "lucide-react";

import { PilotEmptyModule } from "@/components/pilot-empty-module";
import { PILOT_UNAVAILABLE } from "@/components/pilot-unavailable-copy";

export default async function ExpertiseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await params;

  return (
    <PilotEmptyModule
      icon={ShieldCheck}
      title="Карточка экспертизы недоступна"
      description={PILOT_UNAVAILABLE.expertise}
      actionLabel="К списку экспертиз"
      actionHref="/expertise"
    />
  );
}
