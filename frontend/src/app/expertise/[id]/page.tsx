import { ExpertiseDetail } from "./_components/expertise-detail";

export default async function ExpertiseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExpertiseDetail expertiseId={id} />;
}
