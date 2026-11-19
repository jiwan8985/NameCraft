import { Recommendations } from "@/components/naming/recommendations";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Recommendations projectId={id} />;
}
