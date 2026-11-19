"use client";

import { useCallback, useEffect, useState } from "react";
import { ProjectNav, useCandidates } from "@/components/collab/use-project";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Notice, Textarea } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";
import { CATEGORY_ORDER, CATEGORY_SHORT } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
const SENS: Record<string, string> = { low: "낮음", medium: "보통", high: "높음", single_scenario: "단일", not_available: "N/A" };

export function FinalizeView({ projectId }: { projectId: string }) {
  const { items } = useCandidates(projectId);
  const [sel, setSel] = useState<string[]>([]);
  const [board, setBoard] = useState<any>(null);
  const [hist, setHist] = useState<any[]>([]);
  const [chosen, setChosen] = useState("");
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(async () => {
    const [b, d] = await Promise.all([apiFetch<any>(`projects/${projectId}/finalists/board`), apiFetch<any[]>(`projects/${projectId}/decisions`)]);
    setBoard(b.ok ? b.data : null);
    if (d.ok) setHist(d.data);
  }, [projectId]);
  useEffect(() => { load(); }, [load]);

  async function setFinalists() {
    const r = await apiFetch(`projects/${projectId}/finalists`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ candidate_ids: sel }) });
    if (!r.ok) return setMsg(r.error.message);
    setSel([]); load();
  }
  async function decide() {
    const r = await postJson(`projects/${projectId}/decision`, { candidate_id: chosen, reason });
    setMsg(r.ok ? "결정을 기록했습니다. 출생신고 전 공식 인명용 한자 조회로 다시 확인하세요." : r.error.message);
    load();
  }
  return (
    <div className="space-y-4">
      <ProjectNav projectId={projectId} />
      {msg && <Notice role="status">{msg}</Notice>}
      <Card className="space-y-2">
        <CardTitle>결선 후보 고르기 (3~5개)</CardTitle>
        <div className="flex flex-wrap gap-2">{items.map((c) => (
          <label key={c.id} className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-sm">
            <input type="checkbox" checked={sel.includes(c.id!)} onChange={(e) => setSel((s) => e.target.checked ? [...s, c.id!].slice(0, 5) : s.filter((x) => x !== c.id))} />
            {c.full_hangul}</label>))}</div>
        <Button disabled={sel.length < 3} onClick={setFinalists}>결선 보드 만들기</Button>
      </Card>
      {board && (
        <Card className="overflow-x-auto space-y-2">
          <CardTitle>결선 보드</CardTitle>
          <CardDescription>같은 기준(가중치·학파 프로필·현재 출생정보)으로 비교합니다. 공식 한자 판정은 점수와 별도입니다.</CardDescription>
          <table className="w-full min-w-[760px] text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr><th>이름</th><th>한자</th><th>공식 한자</th><th>종합</th>{CATEGORY_ORDER.map((k) => <th key={k}>{CATEGORY_SHORT[k]}</th>)}<th>시간 민감도</th><th>가족 좋아요</th></tr>
            </thead>
            <tbody>{board.finalists.map((f: any) => (
              <tr key={f.id} className="border-t border-border">
                <th scope="row" className="py-1 text-left">{f.full_hangul}{board.chosen_candidate_id === f.id && " ★"}</th>
                <td>{f.given_hanja ?? "—"}</td>
                <td><StatusBadge status={!f.given_hanja ? "hangul_name" : f.gate.official_hanja === "pass" ? "official" : f.gate.official_hanja === "fail" ? "not_listed" : "unverified"} /></td>
                <td className="tabular-nums font-semibold">{f.overall ?? "N/A"}</td>
                {CATEGORY_ORDER.map((k) => <td key={k} className="tabular-nums">{f.categories[k].score ?? "N/A"}</td>)}
                <td>{SENS[f.scenario_sensitivity] ?? f.scenario_sensitivity}</td>
                <td>{f.family ? `${f.family.like_count}/${f.family.voted}` : "—"}</td>
              </tr>))}</tbody>
          </table>
          <div className="grid gap-3 sm:grid-cols-[12rem_1fr_auto] sm:items-end">
            <Field label="최종 선택" htmlFor="chosen"><select id="chosen" className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm" value={chosen} onChange={(e) => setChosen(e.target.value)}>
              <option value="">선택</option>{board.finalists.map((f: any) => <option key={f.id} value={f.id}>{f.full_hangul}</option>)}</select></Field>
            <Field label="선택 이유" htmlFor="reason"><Textarea id="reason" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <Button disabled={!chosen || !reason.trim()} onClick={decide}>결정 기록</Button>
          </div>
          <p className="text-xs text-muted-foreground">선택하지 않은 후보도 그대로 남아 언제든 다시 볼 수 있습니다. 출생신고 준비 점검은 다음 단계에서 추가됩니다.</p>
        </Card>
      )}
      {hist.length > 0 && (
        <Card><CardTitle>결정 기록</CardTitle>
          <ul className="mt-2 text-sm">{hist.map((d) => <li key={d.id}>{d.created_at.slice(0, 16)} · 결선 {d.finalists.length}개 · {d.chosen_candidate_id ? `선택: ${items.find((i) => i.id === d.chosen_candidate_id)?.full_hangul ?? d.chosen_candidate_id} — ${d.reason}` : "선택 전"}{d.is_current ? " · 현재" : ""}</li>)}</ul></Card>
      )}
    </div>
  );
}
