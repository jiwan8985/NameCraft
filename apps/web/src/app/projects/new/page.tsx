import { NewProjectWizard } from "@/components/naming/new-project-wizard";

export default function Page() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-2xl font-semibold">새 작명 프로젝트</h1>
      <NewProjectWizard />
    </div>
  );
}
