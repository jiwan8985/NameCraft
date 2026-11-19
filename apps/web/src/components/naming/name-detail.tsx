"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AnalysisSections } from "@/components/naming/analysis-sections";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Details, Notice } from "@/components/ui/form";
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
  const score = d.ranking.overall;
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Link href={`/projects/${d.project.id}/recommendations`} className="text-sm text-muted-foreground hover:text-foreground">← {d.project.title}</Link>
      <Card className="space-y-4 p-6 text-center">
        <p className="text-4xl font-bold tracking-[0.2em] sm:text-5xl">{n.full_hangul}</p>
        {n.full_hanja && <p className="text-xl tracking-[0.3em] text-muted-foreground">{n.full_hanja}</p>}
        <div className="flex flex-wrap justify-center gap-2 text-sm">
          <span className="rounded-full bg-primary-soft px-3 py-1 font-semibold text-primary">{score === null ? "N/A" : `${Math.round(score)}점`}</span>
          <span className="rounded-full bg-muted px-3 py-1 text-muted-foreground">[{d.analysis.phonetics.pronunciation.pronounced}] 로 읽어요</span>
          {d.analysis.romanization && <span className="rounded-full bg-muted px-3 py-1 text-muted-foreground">{d.analysis.romanization.surname_rr} {d.analysis.romanization.given_rr}</span>}
        </div>
        <p className="mx-auto max-w-xl text-sm leading-relaxed text-muted-foreground">{d.explanation.text}</p>
        <div className="flex flex-wrap justify-center gap-2">
          <Button size="sm" variant="outline" onClick={() => navigator.clipboard?.writeText(`${n.full_hangul} ${n.full_hanja ?? ""}`.trim())}>한글·한자 복사</Button>
          {d.candidate.status === "excluded"
            ? <Button size="sm" onClick={() => setStatus("active")}>다시 추천 허용</Button>
            : <Button size="sm" variant={d.candidate.status === "favorite" ? "default" : "soft"} onClick={() => setStatus(d.candidate.status === "favorite" ? "active" : "favorite")}>
                {d.candidate.status === "favorite" ? "★ 즐겨찾기" : "☆ 즐겨찾기"}</Button>}
        </div>
      </Card>
      {d.candidate.ai_reason && <Card className="text-sm text-muted-foreground">AI 의견(주관): {d.candidate.ai_reason}</Card>}
      <Card>
        <Details summary="점수 근거와 분석 자세히 (발음·뜻·수리·사용성)">
          <AnalysisSections analysis={d.analysis} ranking={d.ranking} />
        </Details>
      </Card>
      {d.generation && (
        <Card>
          <Details summary="이 이름이 만들어진 방법">
            <p className="text-sm">
              {d.generation.provider_id}{d.generation.model_id ? ` · 모델 ${d.generation.model_id}` : ""} · {d.generation.execution_mode}
              {d.generation.prompt_version ? ` · 프롬프트 ${d.generation.prompt_version}` : ""}{d.generation.seed != null ? ` · seed ${d.generation.seed}` : ""}
              {d.generation.fallback_reason ? ` · 대체 사유 ${d.generation.fallback_reason}` : ""}
            </p>
          </Details>
        </Card>
      )}
      {d.reactions.length > 0 && (
        <Card>
          <Details summary={`반응 기록 ${d.reactions.length}개`}>
            <ul className="text-sm">{d.reactions.map((r, i) => <li key={i}>{r.created_at.slice(0, 16)} · {r.reaction}{r.memo ? ` · ${r.memo}` : ""}</li>)}</ul>
          </Details>
        </Card>
      )}
    </div>
  );
}
