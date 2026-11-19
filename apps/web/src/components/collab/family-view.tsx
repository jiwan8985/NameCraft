"use client";

import { useCallback, useEffect, useState } from "react";
import { ProjectNav, useCandidates } from "@/components/collab/use-project";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Input, Notice } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
const R = { like: "좋아요", hold: "보류", dislike: "싫어요" } as const;

export function FamilyView({ projectId }: { projectId: string }) {
  const { items } = useCandidates(projectId);
  const [sum, setSum] = useState<any>(null);
  const [alias, setAlias] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => apiFetch<any>(`projects/${projectId}/family`).then((r) => r.ok && setSum(r.data)), [projectId]);
  useEffect(() => { load(); }, [load]);

  async function addMember() {
    const r = await postJson(`projects/${projectId}/members`, { alias });
    if (!r.ok) return setMsg(r.error.message);
    setAlias(""); load();
  }
  async function vote(member_id: string, candidate_id: string, reaction: string) {
    const r = await postJson("family/votes", { member_id, candidate_id, reaction });
    if (!r.ok) return setMsg(r.error.message);
    load();
  }
  const voteOf = (cid: string, mid: string) => sum?.candidates.find((c: any) => c.candidate_id === cid)?.votes[mid]?.reaction;

  return (
    <div className="space-y-4">
      <ProjectNav projectId={projectId} />
      <Card className="flex flex-wrap items-end gap-2">
        <Field label="구성원 추가 (별칭)" htmlFor="alias" hint="예: 엄마, 아빠 — 실명은 필요 없습니다."><Input id="alias" value={alias} onChange={(e) => setAlias(e.target.value)} /></Field>
        <Button disabled={!alias.trim()} onClick={addMember}>추가</Button>
      </Card>
      {msg && <Notice tone="danger">{msg}</Notice>}
      {sum && sum.members.length === 0 && <Notice>평가할 구성원을 먼저 추가하세요.</Notice>}
      {sum && sum.members.length > 0 && (
        <Card className="overflow-x-auto">
          <CardTitle>각자 평가</CardTitle>
          <CardDescription>구성원의 반응은 후보를 제외시키지 않습니다. 의견 차이를 보기 위한 기록입니다.</CardDescription>
          <table className="mt-2 w-full min-w-[520px] text-sm">
            <thead className="text-left text-xs text-muted-foreground"><tr><th>이름</th>{sum.members.map((m: any) => <th key={m.id}>{m.alias}</th>)}</tr></thead>
            <tbody>{items.map((c) => (
              <tr key={c.id} className="border-t border-border">
                <th scope="row" className="py-1 text-left font-normal">{c.full_hangul} {c.given_hanja ?? ""}</th>
                {sum.members.map((m: any) => (
                  <td key={m.id}><div className="flex gap-1">{(Object.keys(R) as (keyof typeof R)[]).map((r) => (
                    <Button key={r} size="sm" variant={voteOf(c.id!, m.id) === r ? "default" : "outline"} aria-pressed={voteOf(c.id!, m.id) === r}
                            aria-label={`${m.alias} ${c.full_hangul} ${R[r]}`} onClick={() => vote(m.id, c.id!, r)}>{R[r]}</Button>))}</div></td>
                ))}
              </tr>))}
            </tbody>
          </table>
        </Card>
      )}
      {sum && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card><CardTitle>모두 좋아한 이름</CardTitle>
            <ul className="mt-2 text-sm">{sum.common.length ? sum.common.map((c: any) => <li key={c.candidate_id}>{c.given_hangul} {c.given_hanja ?? ""}</li>) : <li className="text-muted-foreground">아직 없음</li>}</ul></Card>
          <Card><CardTitle>의견이 갈린 이름</CardTitle>
            <ul className="mt-2 text-sm">{sum.disagreements.length ? sum.disagreements.map((c: any) => <li key={c.candidate_id}>{c.given_hangul} — 좋아요 {c.like_count}/{c.voted}</li>) : <li className="text-muted-foreground">없음</li>}</ul></Card>
        </div>
      )}
    </div>
  );
}
