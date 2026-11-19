"use client";

import { useCallback, useEffect, useState } from "react";
import { ProjectNav, useCandidates } from "@/components/collab/use-project";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Notice } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
export function TournamentView({ projectId }: { projectId: string }) {
  const { items } = useCandidates(projectId);
  const [sel, setSel] = useState<string[]>([]);
  const [list, setList] = useState<any[]>([]);
  const [cur, setCur] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => apiFetch<any[]>(`projects/${projectId}/tournaments`).then((r) => {
    if (!r.ok) return;
    setList(r.data);
    setCur((c: any) => c ?? r.data.find((t) => t.status === "active") ?? null);
  }), [projectId]);
  useEffect(() => { load(); }, [load]);

  async function start() {
    const r = await postJson<any>("tournaments", { project_id: projectId, candidate_ids: sel });
    if (!r.ok) return setMsg(r.error.message);
    setCur(r.data); setSel([]); load();
  }
  async function vote(i: number, choice: string) {
    const r = await postJson<any>(`tournaments/${cur.id}/vote`, { match_index: i, choice });
    if (!r.ok) return setMsg(r.error.message);
    setCur(r.data); load();
  }
  const round = cur?.rounds[cur.rounds.length - 1] ?? [];
  return (
    <div className="space-y-4">
      <ProjectNav projectId={projectId} />
      {msg && <Notice tone="danger">{msg}</Notice>}
      {(!cur || cur.status === "done") && (
        <Card className="space-y-2">
          <CardTitle>새 토너먼트 (2~16개)</CardTitle>
          <div className="flex flex-wrap gap-2">{items.map((c) => (
            <label key={c.id} className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-sm">
              <input type="checkbox" checked={sel.includes(c.id!)} onChange={(e) => setSel((s) => e.target.checked ? [...s, c.id!].slice(0, 16) : s.filter((x) => x !== c.id))} />
              {c.full_hangul}</label>))}</div>
          <Button disabled={sel.length < 2} onClick={start}>시작</Button>
        </Card>
      )}
      {cur && cur.status === "active" && (
        <Card className="space-y-3">
          <CardTitle>{cur.rounds.length}라운드</CardTitle>
          <CardDescription>둘 중 더 마음에 드는 이름을 고르세요. &lsquo;보류&rsquo;는 둘 다 다음 라운드로 올립니다.</CardDescription>
          {round.map((m: any, i: number) => (
            <div key={i} className="flex flex-wrap items-center gap-2">
              {m.choice === "bye" ? <span className="text-sm">{m.a_name} — 부전승</span> : <>
                <Button variant={m.choice === "a" ? "default" : "outline"} onClick={() => vote(i, "a")}>{m.a_name}</Button>
                <span className="text-xs text-muted-foreground">vs</span>
                <Button variant={m.choice === "b" ? "default" : "outline"} onClick={() => vote(i, "b")}>{m.b_name}</Button>
                <Button size="sm" variant={m.choice === "hold" ? "default" : "ghost"} onClick={() => vote(i, "hold")}>보류</Button></>}
            </div>))}
        </Card>
      )}
      {cur && cur.status === "done" && (
        <Notice role="status">{cur.result.tied ? `결정 보류 — 남은 후보: ${cur.result.finalist_names.join(", ")}` : `우승: ${cur.result.winner_name}`}</Notice>
      )}
      {list.length > 0 && (
        <Card><CardTitle>기록</CardTitle>
          <ul className="mt-2 text-sm">{list.map((t) => <li key={t.id}>{t.created_at.slice(0, 16)} · {t.status === "done" ? (t.result.tied ? "보류 종료" : `우승 ${t.result.winner_name}`) : "진행 중"} · {t.rounds.length}라운드</li>)}</ul></Card>
      )}
    </div>
  );
}
