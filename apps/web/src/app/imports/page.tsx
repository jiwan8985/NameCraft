import { Suspense } from "react";
import { ImportsView } from "@/components/collab/imports-view";
import { routeByPath } from "@/lib/routes";

export default function Page() {
  const r = routeByPath("/imports");
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">{r.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{r.summary} — 해석의 참/거짓이 아니라 같은 공식·입력으로 재현되는지 확인합니다.</p>
      </header>
      <Suspense fallback={<p className="text-sm text-muted-foreground">불러오는 중…</p>}>
        <ImportsView />
      </Suspense>
    </div>
  );
}
