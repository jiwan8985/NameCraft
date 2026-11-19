"use client";

import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Input, Notice, Select } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
const W: Record<string, string> = { rolling_5h: "5시간", weekly: "주간", daily: "일간", model_group: "모델 그룹", other: "기타" };

export function useDemoToggle() {
  const [demo, setDemo] = useState(false);
  return { demo, setDemo, q: demo ? "include_demo=true" : "include_demo=false" };
}

export function DemoBar({ demo, setDemo, onChange }: { demo: boolean; setDemo: (v: boolean) => void; onChange?: () => void }) {
  async function load() { await postJson("ai/usage/demo", {}); setDemo(true); onChange?.(); }
  async function clear() { await apiFetch("ai/usage/demo", { method: "DELETE" }); setDemo(false); onChange?.(); }
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <label className="inline-flex items-center gap-1"><input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} /> DEMO 포함</label>
      <Button size="sm" variant="ghost" onClick={load}>DEMO 불러오기</Button>
      <Button size="sm" variant="ghost" onClick={clear}>DEMO 지우기</Button>
      {demo && <span className="rounded-md border border-mock px-2 py-0.5 text-mock">◆ DEMO DATA 포함 — 실제 사용량 아님</span>}
    </div>
  );
}

function Stat({ label, v, unit }: { label: string; v: number | null | undefined; unit?: string }) {
  return <div><dt className="text-xs text-muted-foreground">{label}</dt><dd className="tabular-nums">{v === null || v === undefined ? "확인 불가" : `${v}${unit ?? ""}`}</dd></div>;
}

export function UsageCenter() {
  const { demo, setDemo, q } = useDemoToggle();
  const [d, setD] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [form, setForm] = useState({ provider_id: "claude_code", window_type: "rolling_5h", used_pct: "", remaining_text: "", reset_at: "", model_group: "all" });
  const load = useCallback(async () => {
    const [s, a] = await Promise.all([apiFetch<any>(`ai/usage/summary?${q}`), apiFetch<any[]>(`ai/alerts?${q}`)]);
    if (s.ok) setD(s.data); else setMsg(s.error.message);
    if (a.ok) setAlerts(a.data);
  }, [q]);
  useEffect(() => { load(); }, [load]);

  async function addQuota() {
    const body: any = { provider_id: form.provider_id, window_type: form.window_type, model_group: form.model_group || "all" };
    if (form.used_pct) body.used_pct = Number(form.used_pct);
    if (form.remaining_text) body.remaining_text = form.remaining_text;
    if (form.reset_at) body.reset_at = new Date(form.reset_at).toISOString();
    const r = await postJson<any>("ai/usage/quotas", body);
    setMsg(r.ok ? (r.data.alerts.length ? r.data.alerts.join(" / ") : "저장했습니다.") : r.error.message);
    load();
  }
  if (!d) return <p aria-busy="true" className="text-sm text-muted-foreground">불러오는 중…</p>;
  return (
    <div className="space-y-4">
      <DemoBar demo={demo} setDemo={setDemo} onChange={load} />
      {d.rules.map((r: string) => <p key={r} className="text-xs text-muted-foreground">• {r}</p>)}
      {msg && <Notice role="status">{msg}</Notice>}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {d.providers.map((p: any) => (
          <Card key={p.provider_id} className="space-y-3">
            <div className="flex items-center justify-between"><CardTitle>{p.label}</CardTitle><span className="text-xs">{p.connection.state ?? "확인 불가"}</span></div>
            <CardDescription>{p.connection.message}</CardDescription>
            <div>
              <p className="flex items-center gap-2 text-sm font-medium">NameCraft 내 사용량 <StatusBadge status="local_observed" /></p>
              <p className="text-xs text-muted-foreground">{p.namecraft_usage.scope}</p>
              <dl className="mt-1 grid grid-cols-3 gap-2 text-sm">
                <Stat label="오늘 요청" v={p.namecraft_usage.today.requests} /><Stat label="7일" v={p.namecraft_usage["7d"].requests} /><Stat label="30일" v={p.namecraft_usage["30d"].requests} />
                <Stat label="성공률(30일)" v={p.namecraft_usage["30d"].success_rate === null ? null : Math.round(p.namecraft_usage["30d"].success_rate * 100)} unit="%" />
                <Stat label="평균 응답" v={p.namecraft_usage["30d"].avg_latency_ms} unit="ms" />
                <Stat label="보고된 출력 토큰" v={p.namecraft_usage["30d"].tokens_out} />
              </dl>
            </div>
            <div>
              <p className="text-sm font-medium">계정 한도</p>
              {p.quota.status === "not_applicable" ? <p className="text-sm">{p.quota.label} <StatusBadge status="not_supported" /></p>
                : p.quota.windows.length === 0 ? <p className="text-sm">{p.quota.label} <StatusBadge status="unknown" /></p>
                : <ul className="space-y-1 text-sm">{p.quota.windows.map((w: any) => (
                    <li key={w.id} className="flex flex-wrap items-center gap-2">
                      <span>{W[w.window_type]}{w.model_group !== "all" ? `·${w.model_group}` : ""}</span>
                      <span className="tabular-nums">{w.used_pct !== null ? `사용 ${w.used_pct}% · 남음 ${w.remaining_pct}%` : w.remaining_text}</span>
                      {w.reset_in_minutes !== null && <span className="text-xs text-muted-foreground">초기화까지 약 {Math.floor(w.reset_in_minutes / 60)}시간 {w.reset_in_minutes % 60}분</span>}
                      <StatusBadge status={w.source_kind} /><span className="text-xs text-muted-foreground">입력 {w.observed_at?.slice(5, 16)}</span>
                    </li>))}</ul>}
            </div>
          </Card>
        ))}
      </div>
      <Card className="space-y-2">
        <CardTitle>구독 한도 직접 입력</CardTitle>
        <CardDescription>Claude Code·Antigravity 의 공식 /usage 화면에 보이는 값을 옮겨 적습니다. 자동 수집은 공식 기계 판독 경로가 없어 하지 않습니다.</CardDescription>
        <div className="grid gap-2 sm:grid-cols-6 sm:items-end">
          <Field label="Provider" htmlFor="qp"><Select id="qp" value={form.provider_id} onChange={(e) => setForm((f) => ({ ...f, provider_id: e.target.value }))}>
            <option value="claude_code">Claude Code</option><option value="antigravity">Antigravity</option></Select></Field>
          <Field label="구간" htmlFor="qw"><Select id="qw" value={form.window_type} onChange={(e) => setForm((f) => ({ ...f, window_type: e.target.value }))}>
            {Object.entries(W).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Select></Field>
          <Field label="모델 그룹" htmlFor="qm"><Input id="qm" value={form.model_group} onChange={(e) => setForm((f) => ({ ...f, model_group: e.target.value }))} /></Field>
          <Field label="사용률(%)" htmlFor="qpct"><Input id="qpct" inputMode="decimal" value={form.used_pct} onChange={(e) => setForm((f) => ({ ...f, used_pct: e.target.value }))} /></Field>
          <Field label="초기화 시각" htmlFor="qr"><Input id="qr" type="datetime-local" value={form.reset_at} onChange={(e) => setForm((f) => ({ ...f, reset_at: e.target.value }))} /></Field>
          <Button onClick={addQuota} disabled={!form.used_pct && !form.remaining_text}>저장</Button>
        </div>
        <Field label="또는 잔여량(화면에 보이는 원본 단위 그대로)" htmlFor="qrt"><Input id="qrt" value={form.remaining_text} onChange={(e) => setForm((f) => ({ ...f, remaining_text: e.target.value }))} /></Field>
      </Card>
      <Card><CardTitle>알림</CardTitle>
        {alerts.length === 0 ? <p className="mt-2 text-sm text-muted-foreground">알림이 없습니다. 공식 사용률이 없는 경우 한도 경고 대신 로컬 요청 증가만 알립니다.</p>
          : <ul className="mt-2 space-y-1 text-sm">{alerts.map((a) => <li key={a.id}>[{a.level}] {a.message} <StatusBadge status={a.is_demo ? "demo" : a.source_kind} /> <span className="text-xs text-muted-foreground">{a.created_at.slice(5, 16)}</span></li>)}</ul>}</Card>
    </div>
  );
}
