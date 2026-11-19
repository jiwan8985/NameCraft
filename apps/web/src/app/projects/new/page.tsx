import { NewProjectWizard } from "@/components/naming/new-project-wizard";

export default function Page() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">새 이름 짓기</h1>
        <p className="mt-1 text-muted-foreground">세 단계면 끝나요.</p>
      </div>
      <NewProjectWizard />
    </div>
  );
}
