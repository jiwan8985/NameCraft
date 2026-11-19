import { Suspense } from "react";
import { ProjectGate } from "@/components/collab/project-gate";
import { routeByPath } from "@/lib/routes";

export default function Page() {
  const r = routeByPath("/family");
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">{r.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{r.summary}</p>
      </header>
      <Suspense fallback={<p className="text-sm text-muted-foreground">불러오는 중…</p>}>
        <ProjectGate view="family" />
      </Suspense>
    </div>
  );
}
