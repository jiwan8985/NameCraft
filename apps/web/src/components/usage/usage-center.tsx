"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Activity, Bell, Clock3, Cpu, Layers, RefreshCw } from "lucide-react";
import { LineChart, type ChartPoint } from "@/components/usage/charts";
import { StatusBadge } from "@/components/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Notice } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";

type WindowStats = { requests: number; success_rate: number | null; avg_latency_ms: number | null; tokens_out: number | null };
type Usage = {
  provider_id: string;
  namecraft_usage: { today: WindowStats; "7d": WindowStats; "30d": WindowStats };
};
type UsageAlert = { id: string; provider_id: string; message: string; created_at: string };
type Trend = { series: { ollama?: ChartPoint[] }; unit: string };

const number = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 });
function display(value: number | null | undefined, suffix = "") {
  return value == null ? "확인 불가" : number.format(value) + suffix;
}

export function UsageCenter() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [trend, setTrend] = useState<Trend | null>(null);
  const [alerts, setAlerts] = useState<UsageAlert[]>([]);
  const [error, setError] = useState("");
  const [trendError, setTrendError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setTrendError("");
    const [summary, requests, events] = await Promise.all([
      apiFetch<{ providers: Usage[] }>("ai/usage/summary?provider=ollama"),
      apiFetch<Trend>("ai/usage/timeseries?metric=requests&days=7"),
      apiFetch<UsageAlert[]>("ai/alerts"),
    ]);
    if (summary.ok) setUsage(summary.data.providers.find((provider) => provider.provider_id === "ollama") ?? null);
    else setError(summary.error.message);
    if (requests.ok) setTrend(requests.data);
    else setTrendError(requests.error.message);
    if (events.ok) setAlerts(events.data.filter((event) => event.provider_id === "ollama"));
    setLoading(false);
  }, []);
  useEffect(() => { void load(); }, [load]);

  const stats = usage?.namecraft_usage;
  const month = stats?.["30d"];
  const cards = [
    { label: "최근 24시간", value: display(stats?.today.requests, "건"), icon: Activity, detail: `최근 7일 ${display(stats?.["7d"].requests, "건")}` },
    { label: "최근 30일 요청", value: display(month?.requests, "건"), icon: Layers, detail: month?.success_rate == null ? "성공률 확인 불가" : `성공률 ${display(month.success_rate * 100, "%")}` },
    { label: "평균 응답 시간", value: display(month?.avg_latency_ms == null ? null : month.avg_latency_ms / 1000, "초"), icon: Clock3, detail: "최근 30일" },
    { label: "출력 토큰", value: display(month?.tokens_out), icon: Cpu, detail: "최근 30일 · 모델 보고값" },
  ];

  return (
    <div className="usage-surface space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm font-medium">
          <span className="text-primary">Ollama</span> <StatusBadge status="local_observed" />
        </p>
        <Button variant="outline" size="sm" onClick={() => { void load(); }} disabled={loading}>
          <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" /> 새로고침
        </Button>
      </div>
      {error && <Notice role="alert" tone="danger">{error}</Notice>}
      {loading && !usage && <p role="status" className="text-sm text-muted-foreground">사용량을 불러오고 있어요.</p>}
      {usage && (
        <>
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {cards.map(({ label, value, icon: Icon, detail }) => (
              <Card key={label} className="usage-stat min-w-0 space-y-2 p-3 sm:p-4">
                <dt className="flex items-center gap-2 text-xs text-muted-foreground sm:text-sm">
                  <Icon className="size-4 shrink-0 text-primary" aria-hidden="true" /> {label}
                </dt>
                <dd className="break-words text-xl font-semibold tracking-tight tabular-nums sm:text-[2rem]">{value}</dd>
                <dd className="text-xs text-muted-foreground">{detail}</dd>
              </Card>
            ))}
          </dl>

          <Card className="space-y-4 border-border bg-card">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><CardTitle>최근 7일 요청</CardTitle><CardDescription className="mt-1">이 앱에서 실행한 Ollama 요청을 집계합니다.</CardDescription></div>
              <Link className={buttonVariants({ variant: "outline", size: "sm" })} href="/ai/analytics">모델별 분석</Link>
            </div>
            {trendError ? <Notice role="alert" tone="danger">{trendError}</Notice>
              : trend && <LineChart points={trend.series?.ollama ?? []} unit={trend.unit} label="날짜별 요청 수" variant="bars" />}
          </Card>

          <Card className="space-y-3">
            <CardTitle className="flex items-center gap-2"><Bell className="size-4 text-primary" aria-hidden="true" /> 알림</CardTitle>
            {alerts.length === 0 ? <p className="text-sm text-muted-foreground">로컬 AI 사용량 알림이 없어요.</p>
              : <ul className="divide-y divide-border text-sm">{alerts.map((event) => (
                <li key={event.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <span>{event.message}</span><time dateTime={event.created_at} className="text-xs text-muted-foreground">{event.created_at.slice(5, 16).replace("T", " ")}</time>
                </li>
              ))}</ul>}
          </Card>
        </>
      )}
    </div>
  );
}
