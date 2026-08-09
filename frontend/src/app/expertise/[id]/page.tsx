import { ExpertiseHeader } from "@/components/dashboard/expertise-header";
import { ExpertiseTabs } from "@/components/dashboard/expertise-tabs";

export default async function ExpertiseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await params;
  return (
    <div className="space-y-6">
      <ExpertiseHeader />
      <ExpertiseTabs />
    </div>
  );
}
