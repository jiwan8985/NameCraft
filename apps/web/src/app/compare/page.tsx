import { Suspense } from "react";
import { CompareView } from "@/components/naming/compare-view";

export default function Page() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">후보 비교</h1>
      <Suspense fallback={<p className="text-sm text-muted-foreground">불러오는 중…</p>}>
        <CompareView />
      </Suspense>
    </div>
  );
}
