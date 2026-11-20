"use client";

import { useCallback, useEffect, useState } from "react";
import { ProjectNav } from "@/components/collab/use-project";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Input, Notice, Select, splitList } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";
import type { Project, Warning } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
const SENS = { low: "시간 민감도 낮음", medium: "보통", high: "높음", single_scenario: "단일 시나리오", not_available: "N/A" } as Record<string, string>;

export function ScenarioView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [cur, setCur] = useState<any>(null);
  const [hist, setHist] = useState<any[]>([]);
  const [warn, setWarn] = useState<Warning[]>([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [f, setF] = useState({ kind: "expected", calendar: "solar", date: "", leap: false, mode: "unknown", time: "", from: "09:00",
                               to: "12:00", window: 0, extra: "", tst: "off", lon: "", zi: "jojasi_next_day" });
  const set = (k: string, v: unknown) => setF((x) => ({ ...x, [k]: v }));

  const load = useCallback(async () => {
    const [p, s, h] = await Promise.all([apiFetch<Project>(`projects/${projectId}`), apiFetch<any>(`projects/${projectId}/scenario`),
                                         apiFetch<any[]>(`projects/${projectId}/birth-profiles`)]);
    if (p.ok) setProject(p.data);
    if (s.ok) { setCur(s.data); setWarn(s.warnings); }
    if (h.ok) setHist(h.data);
  }, [projectId]);
  useEffect(() => { load(); }, [load]);

  async function save() {
    setMsg(null);
    setSaving(true);
    const body: any = { kind: f.kind, calendar: f.calendar, date: f.date, is_leap_month: f.leap, true_solar_time: f.tst,
                        zi_convention: f.zi, longitude: f.lon ? Number(f.lon) : null };
    if (f.mode === "exact") body.time = f.time;
    if (f.mode === "range") body.time_range = [f.from, f.to];
    if (f.kind === "expected") { body.day_window = Number(f.window); body.extra_dates = splitList(f.extra); }
    const r = await postJson<any>(`projects/${projectId}/birth-profiles`, body);
    setSaving(false);
    if (!r.ok) return setMsg(r.error.message);
    setMsg(f.kind === "actual" ? "실제 출생정보로 다시 평가했습니다. 이전 기록은 아래 이력에 남아 있습니다." : "저장했습니다.");
    load();
  }
  async function toggleSaju() {
    const next = !project?.preferences.use_saju;
    await postJson(`projects/${projectId}`, { preferences: { use_saju: next } }, "PATCH");
    await apiFetch(`projects/${projectId}/scenario?refresh=true`);
    load();
  }
  const s = cur?.scenario;
  return (
    <div className="space-y-4">
      <ProjectNav projectId={projectId} />
      <Card className="space-y-3">
        <h1 className="text-xl font-semibold">아기 출생정보</h1>
        <CardDescription>아직 태어나기 전이라면 예정일을 넣어 살펴보세요. 태어난 뒤 실제 날짜와 시각으로 다시 계산할 수 있어요.</CardDescription>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="구분" htmlFor="kind"><Select id="kind" value={f.kind} onChange={(e) => set("kind", e.target.value)}>
            <option value="expected">출생 예정</option><option value="actual">실제 출생(확정)</option></Select></Field>
          <Field label="달력" htmlFor="cal"><Select id="cal" value={f.calendar} onChange={(e) => set("calendar", e.target.value)}>
            <option value="solar">양력</option><option value="lunar">음력</option></Select></Field>
          <Field label="날짜" htmlFor="date"><Input id="date" type="date" value={f.date} onChange={(e) => set("date", e.target.value)} /></Field>
          {f.calendar === "lunar" && <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={f.leap} onChange={(e) => set("leap", e.target.checked)} /> 윤달</label>}
          <Field label="시각" htmlFor="mode"><Select id="mode" value={f.mode} onChange={(e) => set("mode", e.target.value)}>
            <option value="exact">정확한 시각</option><option value="range">시간 구간</option><option value="unknown">모름</option></Select></Field>
          {f.mode === "exact" && <Field label="시각" htmlFor="time"><Input id="time" type="time" value={f.time} onChange={(e) => set("time", e.target.value)} /></Field>}
          {f.mode === "range" && <Field label="구간" htmlFor="from"><div className="flex gap-1"><Input id="from" type="time" value={f.from} onChange={(e) => set("from", e.target.value)} /><Input aria-label="끝 시각" type="time" value={f.to} onChange={(e) => set("to", e.target.value)} /></div></Field>}
          {f.kind === "expected" && <>
            <Field label="예정일 앞뒤 (일)" htmlFor="win"><Select id="win" value={f.window} onChange={(e) => set("window", e.target.value)}>
              {[0, 1, 2, 3, 5, 7].map((n) => <option key={n} value={n}>±{n}</option>)}</Select></Field>
            <Field label="다른 후보 예정일 (양력, 쉼표)" htmlFor="extra"><Input id="extra" placeholder="2027-01-20" value={f.extra} onChange={(e) => set("extra", e.target.value)} /></Field>
          </>}
        </div>
        <details className="rounded-md border border-border p-3 text-sm">
          <summary className="cursor-pointer font-medium">계산 기준 (학파 옵션)</summary>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            <Field label="시각 기준" htmlFor="tst"><Select id="tst" value={f.tst} onChange={(e) => set("tst", e.target.value)}>
              <option value="off">표준시</option><option value="longitude_only">지방평균시</option><option value="with_equation_of_time">진태양시</option></Select></Field>
            {f.tst !== "off" && <Field label="출생지 경도" htmlFor="lon" hint="서울 약 126.98"><Input id="lon" value={f.lon} onChange={(e) => set("lon", e.target.value)} /></Field>}
            <Field label="자시" htmlFor="zi"><Select id="zi" value={f.zi} onChange={(e) => set("zi", e.target.value)}>
              <option value="jojasi_next_day">조자시(23시부터 다음 날)</option><option value="yajasi_same_day">야자시</option></Select></Field>
          </div>
        </details>
        <Button disabled={saving || !f.date || (f.mode === "exact" && !f.time) || (f.mode === "range" && (!f.from || !f.to))} onClick={save}>{saving ? "계산 중…" : "저장하고 계산"}</Button>
        {msg && <Notice role="status">{msg}</Notice>}
      </Card>

      {warn.map((w) => <Notice key={w.code} tone="warn">{w.message}</Notice>)}

      {s && (
        <Card className="space-y-3">
          <CardTitle>시나리오 {s.scenario_count}개 · 서로 다른 명식 {s.distinct_charts}개</CardTitle>
          <CardDescription>{cur.profile.kind === "actual" ? "확정 출생정보" : "예정"} · 바뀌는 기둥: {s.varying_pillars.join(", ") || "없음"}</CardDescription>
          {s.notes.map((n: string) => <p key={n} className="text-xs text-muted-foreground">{n}</p>)}
          <table className="w-full text-sm">
            <caption className="sr-only">오행 개수 범위</caption>
            <thead className="text-left text-xs text-muted-foreground"><tr><th>오행</th>{Object.keys(s.element_ranges).map((e) => <th key={e}>{e}</th>)}</tr></thead>
            <tbody><tr><th scope="row" className="text-left font-normal">최소~최대</th>{Object.values(s.element_ranges).map((v: any, i) => <td key={i}>{v.min}~{v.max}</td>)}</tr></tbody>
          </table>
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-card text-left text-xs text-muted-foreground"><tr><th>날짜</th><th>구간</th><th>4주</th><th>바뀐 기둥</th></tr></thead>
              <tbody>{s.scenarios.map((x: any) => (
                <tr key={x.id} className="border-t border-border"><td>{x.date}{x.offset_days ? ` (${x.offset_days > 0 ? "+" : ""}${x.offset_days})` : ""}</td>
                  <td className="text-xs">{x.from_local.slice(11, 16)}–{x.to_local.slice(11, 16)}</td><td>{x.text}</td><td className="text-xs">{x.changed.join(", ")}</td></tr>))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card className="space-y-2">
        <CardTitle>사주 기반 이름 해석 (선택)</CardTitle>
        <CardDescription>{s?.interpretation?.disclaimer ?? "한 학파의 단순 보완설에 따른 참고 해석입니다."}</CardDescription>
        <Button size="sm" variant="outline" onClick={toggleSaju}>{project?.preferences.use_saju ? "사용 안 함" : "사용하기"}</Button>
        {s?.names?.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground"><tr><th>이름</th><th>최소</th><th>최대</th><th>민감도</th></tr></thead>
            <tbody>{s.names.map((n: any) => <tr key={n.label} className="border-t border-border"><td>{n.label}</td><td>{n.min ?? "N/A"}</td><td>{n.max ?? "N/A"}</td><td>{SENS[n.sensitivity] ?? n.sensitivity}</td></tr>)}</tbody>
          </table>
        )}
      </Card>

      {hist.length > 0 && (
        <Card>
          <CardTitle>출생정보 이력</CardTitle>
          <ul className="mt-2 space-y-1 text-sm">{hist.map((h) => (
            <li key={h.id}>{h.created_at.slice(0, 16)} · {h.kind === "actual" ? "확정" : "예정"} {h.date} {h.time ?? (h.time_range ? h.time_range.join("~") : "시간 미정")}
              {h.is_current ? " · 현재" : ` · 대체됨 ${h.superseded_at?.slice(0, 10)}`} · 스냅샷 {h.snapshots.length}개</li>))}</ul>
        </Card>
      )}
    </div>
  );
}
