"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { Heatmap, LineChart, ModelBars, type ChartPoint, type ModelActivity } from "@/components/usage/charts";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Notice, Select } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";

const METRICS = {
  requests: "요청 수",
  latency_ms: "평균 응답 시간",
  tokens_in: "입력 토큰",
  tokens_out: "출력 토큰",
};

type Series = { unit: string; series: { ollama?: ChartPoint[] } };
type Activity = { weekday_hour: number[][]; weekdays: string[]; model_distribution: ModelActivity[] };

export function AnalyticsView() {
  const [metric, setMetric] = useState<keyof typeof METRICS>("requests");
  const [days, setDays] = useState(7);
  const [series, setSeries] = useState<Series | null>(null);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [seriesError, setSeriesError] = useState("");
  const [activityError, setActivityError] = useState("");

  useEffect(() => {
    let active = true;
    setSeries(null);
    setSeriesError("");
    apiFetch<Series>(`ai/usage/timeseries?metric=${metric}&days=${days}`).then((result) => {
      if (!active) return;
      if (result.ok) setSeries(result.data);
      else setSeriesError(result.error.message);
    });
    return () => { active = false; };
  }, [metric, days]);

  useEffect(() => {
    let active = true;
    setActivity(null);
    setActivityError("");
    apiFetch<Activity>(`ai/usage/heatmap?days=${days}&provider=ollama`).then((result) => {
      if (!active) return;
      if (result.ok) setActivity(result.data);
      else setActivityError(result.error.message);
    });
    return () => { active = false; };
  }, [days]);

  return (
    <div className="usage-surface space-y-5">
      <Card className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <CardTitle>일별 사용 추이</CardTitle>
            <CardDescription className="mt-1">최근 {days}일 · Ollama</CardDescription>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <Field label="그래프 지표" htmlFor="m">
              <Select id="m" value={metric} onChange={(e) => setMetric(e.target.value as keyof typeof METRICS)} className="min-w-32">
                {Object.entries(METRICS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </Select>
            </Field>
            <div role="group" aria-label="분석 기간" className="flex gap-1 rounded-xl bg-muted p-1">
              {[7, 30, 90].map((n) => (
                <button key={n} type="button" aria-pressed={days === n} onClick={() => setDays(n)}
                        className={`rounded-lg px-3 py-2 text-sm ${days === n ? "bg-card font-semibold text-primary shadow-sm" : "text-muted-foreground hover:text-foreground"}`}>
                  {n}일
                </button>
              ))}
            </div>
          </div>
        </div>
        {seriesError ? <Notice role="alert" tone="danger">{seriesError}</Notice>
          : series ? <LineChart points={series.series.ollama ?? []} unit={series.unit} label={METRICS[metric]} variant={metric === "latency_ms" ? "line" : "bars"} />
          : <p role="status" className="text-sm text-muted-foreground">그래프를 불러오고 있어요.</p>}
      </Card>

      {activityError && <Notice role="alert" tone="danger">{activityError}</Notice>}
      {activity && (
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <Card className="usage-stat min-w-0"><CardTitle>요일·시간대</CardTitle><Heatmap grid={activity.weekday_hour} rows={activity.weekdays} /></Card>
          <Card className="usage-stat min-w-0"><CardTitle>모델별 사용 비중</CardTitle><ModelBars models={activity.model_distribution} /></Card>
        </div>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        {["csv", "json"].map((format) => (
          <a key={format} className={buttonVariants({ variant: "outline", size: "sm" })} href={`/api/proxy/ai/usage/export?format=${format}&provider=ollama`}>
            <Download className="size-4" aria-hidden="true" /> {format.toUpperCase()} 내보내기
          </a>
        ))}
      </div>
    </div>
  );
}
