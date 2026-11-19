import { AnalyticsView } from "@/components/usage/analytics-view";
import { routeByPath } from "@/lib/routes";

export default function Page() {
  const r = routeByPath("/ai/analytics");
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">{r.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{r.summary}</p>
      </header>
      <AnalyticsView />
    </div>
  );
}
