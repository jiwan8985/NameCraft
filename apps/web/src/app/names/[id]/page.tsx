import { NameDetail } from "@/components/naming/name-detail";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <NameDetail id={id} />;
}
