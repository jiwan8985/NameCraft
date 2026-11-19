import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { routeByPath } from "@/lib/routes";

/** Phase 1: 라우트 뼈대. 실제 기능은 route.phase 에서 구현된다. */
export function PlaceholderPage({ path }: { path: string }) {
  const r = routeByPath(path);
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">{r.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{r.summary}</p>
      </header>
      <Card>
        <CardTitle>준비 중인 화면</CardTitle>
        <CardDescription className="mt-1">
          이 화면은 Phase {r.phase}에서 구현됩니다. 현재는 화면 구조만 준비되어 있습니다.
        </CardDescription>
      </Card>
    </div>
  );
}
