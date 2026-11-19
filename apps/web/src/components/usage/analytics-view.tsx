"use client";

import { useCallback, useEffect, useState } from "react";
import { Heatmap, LineChart } from "@/components/usage/charts";
import { DemoBar, useDemoToggle } from "@/components/usage/usage-center";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
const LABELS: Record<string, string> = { ollama: "Ollama", claude_code: "Claude Code", antigravity: "Google Antigravity" };
const METRIC: Record<string, string> = { requests: "요청 수", tokens_in: "입력 토큰(보고값)", tokens_out: "출력 토큰(보고값)", latency_ms: "평균 응답 시간" };

export function AnalyticsView() {
  const { demo, setDemo, q } = useDemoToggle();
  const [metric, setMetric] = useState("requests");
  const [days, setDays] = useState(7);
  const [ts, setTs] = useState<any>(null);
  const [hm, setHm] = useState<any>(null);
  const [table, setTable] = useState(false);
  const load = useCallback(() => {
    apiFetch<any>(`ai/usage/timeseries?metric=${metric}&days=${days}&${q}`).then((r) => r.ok && setTs(r.data));
    apiFetch<any>(`ai/usage/heatmap?days=${days}&${q}`).then((r) => r.ok && setHm(r.data));
  }, [metric, days, q]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="space-y-4">
      <DemoBar demo={demo} setDemo={setDemo} onChange={load} />
      <Card className="grid gap-2 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <Field label="지표" htmlFor="m"><Select id="m" value={metric} onChange={(e) => setMetric(e.target.value)}>{Object.entries(METRIC).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Select></Field>
        <Field label="기간" htmlFor="d"><Select id="d" value={days} onChange={(e) => setDays(Number(e.target.value))}>{[7, 30, 90].map((n) => <option key={n} value={n}>{n}일</option>)}</Select></Field>
        <label className="inline-flex items-center gap-1 text-sm"><input type="checkbox" checked={table} onChange={(e) => setTable(e.target.checked)} /> 표로 보기</label>
      </Card>
      {ts && (
        <>
          <p className="text-xs text-muted-foreground">{ts.note}</p>
          <div className="grid gap-4 md:grid-cols-3">
            {Object.entries(ts.series).map(([pid, pts]: [string, any]) => (
              <Card key={pid}><CardTitle className="text-sm">{LABELS[pid]} — {METRIC[metric]}</CardTitle>
                {table ? (
                  <table className="mt-2 w-full text-xs"><tbody>{pts.map((p: any) => <tr key={p.date}><td>{p.date}</td><td className="text-right tabular-nums">{p.value ?? "값 없음"}</td></tr>)}</tbody></table>
                ) : <LineChart points={pts} unit={ts.unit} label={`${LABELS[pid]} ${METRIC[metric]}`} />}
              </Card>
            ))}
          </div>
        </>
      )}
      {hm && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card><CardTitle className="text-sm">요일·시간대 (전체 Provider 요청 건수)</CardTitle><CardDescription>건수만 셉니다(단위가 같은 요청 수).</CardDescription><Heatmap grid={hm.weekday_hour} rows={hm.weekdays} /></Card>
          <Card><CardTitle className="text-sm">모델별 요청</CardTitle>
            <ul className="mt-2 space-y-1 text-sm">{hm.model_distribution.map((m: any) => <li key={m.provider_id + m.model_id}>{LABELS[m.provider_id]} · {m.model_id} — {m.requests}건</li>)}</ul></Card>
        </div>
      )}
      <Card className="flex flex-wrap gap-3 text-sm"><a className="underline" href={`/api/proxy/ai/usage/export?format=csv&${q}`}>CSV 내보내기</a><a className="underline" href={`/api/proxy/ai/usage/export?format=json&${q}`}>JSON 내보내기</a></Card>
    </div>
  );
}
