import { Suspense } from "react";
import { ReportsView } from "@/components/reports/reports-view";
import { routeByPath } from "@/lib/routes";

export default function Page() {
  const r = routeByPath("/reports");
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">{r.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">보고서(인쇄·PDF), CSV·JSON 내보내기, 백업·복원, 데이터 삭제</p>
      </header>
      <Suspense fallback={<p className="text-sm text-muted-foreground">불러오는 중…</p>}><ReportsView /></Suspense>
    </div>
  );
}
