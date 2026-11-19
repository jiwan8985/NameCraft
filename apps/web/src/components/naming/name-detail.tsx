"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AnalysisSections } from "@/components/naming/analysis-sections";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Notice } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";
import type { RankedItem } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Detail = { candidate: any; project: any; analysis: any; ranking: RankedItem; reactions: any[]; generation: any;
                explanation: { text: string; source: string } };

export function NameDetail({ id }: { id: string }) {
  const [d, setD] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    const r = await apiFetch<Detail>(`candidates/${id}`);
    if (r.ok) setD(r.data); else setError(r.error.message);
  }, [id]);
  useEffect(() => { load(); }, [load]);

  async function setStatus(status: string) {
    const r = await postJson(`candidates/${id}`, { status }, "PATCH");
    if (r.ok) load(); else setError(r.error.message);
  }

  if (error) return <Notice tone="danger" role="alert">{error}</Notice>;
  if (!d) return <p aria-busy="true" className="text-sm text-muted-foreground">불러오는 중…</p>;
  const n = d.analysis.name;
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-sm"><Link href={`/projects/${d.project.id}/recommendations`} className="text-muted-foreground hover:underline">← {d.project.title}</Link></p>
          <h1 className="text-3xl font-semibold">{n.full_hangul} <span className="text-xl text-muted-foreground">{n.full_hanja ?? ""}</span></h1>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => navigator.clipboard?.writeText(`${n.full_hangul} ${n.full_hanja ?? ""}`.trim())}>한글·한자 복사</Button>
          {d.candidate.status === "excluded"
            ? <Button size="sm" onClick={() => setStatus("active")}>다시 추천 허용</Button>
            : <Button size="sm" variant="outline" onClick={() => setStatus(d.candidate.status === "favorite" ? "active" : "favorite")}>
                {d.candidate.status === "favorite" ? "즐겨찾기 해제" : "즐겨찾기"}</Button>}
        </div>
      </header>
      <Card>
        <CardTitle>요약</CardTitle>
        <p className="mt-2 text-sm">{d.explanation.text}</p>
        <CardDescription className="mt-1">계산 결과를 옮긴 자동 문장입니다(AI 해설 아님).</CardDescription>
      </Card>
      {d.generation && (
        <Card>
          <CardTitle>생성 출처</CardTitle>
          <p className="mt-1 text-sm">
            {d.generation.provider_id}{d.generation.model_id ? ` · 모델 ${d.generation.model_id}` : ""} · {d.generation.execution_mode}
            {d.generation.prompt_version ? ` · 프롬프트 ${d.generation.prompt_version}` : ""}{d.generation.seed != null ? ` · seed ${d.generation.seed}` : ""}
            {d.generation.fallback_reason ? ` · 대체 사유 ${d.generation.fallback_reason}` : ""}
          </p>
          {d.candidate.ai_reason && <p className="mt-1 text-sm text-muted-foreground">AI 의견(주관): {d.candidate.ai_reason}</p>}
        </Card>
      )}
      <AnalysisSections analysis={d.analysis} ranking={d.ranking} />
      {d.reactions.length > 0 && (
        <Card>
          <CardTitle>반응 기록</CardTitle>
          <ul className="mt-2 text-sm">{d.reactions.map((r, i) => <li key={i}>{r.created_at.slice(0, 16)} · {r.reaction}{r.memo ? ` · ${r.memo}` : ""}</li>)}</ul>
        </Card>
      )}
    </div>
  );
}
