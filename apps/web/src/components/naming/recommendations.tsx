"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Heart, Info, Loader2, Plus, Sparkles, X } from "lucide-react";
import { ProjectNav } from "@/components/collab/use-project";
import { ConsentDialog, type ConsentPreview } from "@/components/consent-dialog";
import { CategoryBars } from "@/components/score";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Chip, Details, Input, Notice, Select } from "@/components/ui/form";
import { useAIOptions } from "@/lib/ai";
import { apiFetch, postJson } from "@/lib/api";
import type { Project, RankedItem, Warning } from "@/lib/types";
import { cn } from "@/lib/utils";

const SORTS = [["overall", "추천순"], ["phonetic", "발음"], ["meaning", "의미"], ["numerology", "전통 수리"], ["usability", "쓰기 편함"], ["preference", "내 취향"]] as const;
const SOURCE_LABEL: Record<string, string> = { rule_based: "자동 추천", data_based: "예시 기반", ai_based: "AI 제안", user: "직접 추가" };

type ListData = { items: RankedItem[]; weights_normalized: Record<string, number>; ranking_version: string };

function scoreTone(v: number | null) {
  if (v === null) return "bg-muted text-muted-foreground";
  return v >= 85 ? "bg-ok-soft text-ok" : v >= 70 ? "bg-primary-soft text-primary" : "bg-warn-soft text-warn";
}

export function CandidateCard({ item, selected, onSelect, onReact }: {
  item: RankedItem; selected: boolean; onSelect: (v: boolean) => void; onReact: (r: "like" | "dislike" | "hold") => void;
}) {
  const liked = item.reaction === "like";
  return (
    <Card aria-label={item.full_hangul} className={cn("flex flex-col gap-3 transition hover:shadow-md", liked && "ring-2 ring-primary/40")}>
      <div className="flex items-start justify-between gap-2">
        <Link href={`/names/${item.id}`} className="group">
          <p className="text-2xl font-bold tracking-wide group-hover:text-primary">{item.full_hangul}</p>
          <p className="text-sm text-muted-foreground">{item.given_hanja ?? "한글 이름"}</p>
        </Link>
        <span className={cn("rounded-full px-3 py-1 text-sm font-semibold tabular-nums", scoreTone(item.overall))}>
          {item.overall === null ? "N/A" : `${Math.round(item.overall)}점`}
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5 text-[11px]">
        <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">{SOURCE_LABEL[item.source ?? ""] ?? item.source}</span>
        {item.given_hanja && item.gate.official_hanja === "fail" && <span className="rounded-full bg-danger-soft px-2 py-0.5 text-danger">공식 미수록</span>}
        {item.gate.caution === "review" && <span className="rounded-full bg-warn-soft px-2 py-0.5 text-warn">검토 권장</span>}
      </div>
      {item.ai_reason && <p className="text-xs italic text-muted-foreground">AI 의견(주관): {item.ai_reason}</p>}
      <Details summary="점수 자세히">
        <CategoryBars categories={item.categories} />
        {item.incomplete.length > 0 && <p className="mt-2 text-[11px] text-muted-foreground">N/A = 근거 자료가 없어 계산하지 않은 항목(0점 아님)</p>}
      </Details>
      <div className="mt-auto flex items-center gap-1.5 pt-1">
        <Button size="sm" variant={liked ? "default" : "soft"} aria-pressed={liked} aria-label="좋아요" onClick={() => onReact("like")}>
          <Heart className={cn("h-3.5 w-3.5", liked && "fill-current")} /> 좋아요
        </Button>
        <Button size="sm" variant="ghost" aria-pressed={item.reaction === "hold"} aria-label="보류" onClick={() => onReact("hold")}>보류</Button>
        <Button size="sm" variant="ghost" aria-pressed={item.reaction === "dislike"} aria-label="싫어요" onClick={() => onReact("dislike")}><X className="h-3.5 w-3.5" /></Button>
        <label className="ml-auto inline-flex cursor-pointer items-center gap-1 text-xs text-muted-foreground">
          <input type="checkbox" className="accent-[var(--primary)]" checked={selected} onChange={(e) => onSelect(e.target.checked)} /> 비교
        </label>
      </div>
    </Card>
  );
}

export function Recommendations({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [data, setData] = useState<ListData | null>(null);
  const [warnings, setWarnings] = useState<Warning[]>([]);
  const [sort, setSort] = useState("overall");
  const [onlyLiked, setOnlyLiked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState("none");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [consent, setConsent] = useState<ConsentPreview | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [manual, setManual] = useState({ hangul: "", hanja: "" });
  const { opts, hasOff } = useAIOptions();

  const load = useCallback(async () => {
    const [p, c] = await Promise.all([apiFetch<Project>(`projects/${projectId}`),
                                      apiFetch<ListData>(`projects/${projectId}/candidates?sort=${sort}`)]);
    if (!p.ok) return setError(p.error.message);
    if (!c.ok) return setError(c.error.message);
    setProject(p.data);
    setData(c.data);
    setWarnings(c.warnings);
  }, [projectId, sort]);
  useEffect(() => { load(); }, [load]);

  async function generate(withConsent = false) {
    setBusy(true);
    setNotice(null);
    const r = await postJson<{ provider_used: string; saved: unknown[]; fallback_reason: string | null }>(
      `projects/${projectId}/candidates/generate`, { provider, consent: withConsent });
    setBusy(false);
    if (!r.ok) {
      if (r.error.details?.consent_required) return setConsent(r.error.details.preview as ConsentPreview);
      return setNotice(r.error.message);
    }
    const who = r.data.provider_used === "rule_based" ? "자동 추천" : r.data.provider_used;
    setNotice(`새 후보 ${r.data.saved.length}개를 추가했어요 (${who}${r.data.fallback_reason ? " — AI를 쓸 수 없어 자동 추천으로 대신했어요" : ""}).`);
    load();
  }
  async function react(id: string, reaction: "like" | "dislike" | "hold") {
    const r = await postJson("reactions", { candidate_id: id, reaction });
    if (!r.ok) return setNotice(r.error.message);
    load();
  }
  async function addManual() {
    const r = await postJson(`projects/${projectId}/candidates`, { given_hangul: manual.hangul, given_hanja: manual.hanja || null });
    if (!r.ok) return setNotice(r.error.message);
    setManual({ hangul: "", hanja: "" });
    load();
  }

  const items = useMemo(() => (data?.items ?? []).filter((i) => !onlyLiked || i.reaction === "like"), [data, onlyLiked]);
  const likedCount = (data?.items ?? []).filter((i) => i.reaction === "like").length;

  if (error) return <Notice tone="danger" role="alert">{error}</Notice>;
  if (!project || !data) return <p aria-busy="true" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…</p>;

  return (
    <div className="space-y-5">
      <header className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{project.title}</h1>
            <p className="text-sm text-muted-foreground">후보 {data.items.length}개 · 좋아요 {likedCount}개</p>
          </div>
          {selected.length >= 2 && (
            <Link href={`/compare?project=${projectId}&ids=${selected.join(",")}`}><Button variant="soft">선택한 {selected.length}개 비교</Button></Link>
          )}
        </div>
        <ProjectNav projectId={projectId} />
      </header>

      <Card className="flex flex-wrap items-center gap-2 p-3 [&>*]:min-w-0">
        <Button disabled={busy} onClick={() => generate(false)}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} 후보 더 받기
        </Button>
        <Select aria-label="생성 방식" value={provider} onChange={(e) => setProvider(e.target.value)} className="w-auto rounded-full py-2">
          {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </Select>
        {hasOff && opts.length === 1 && <Link href="/settings" className="text-xs text-muted-foreground underline">AI 를 쓰려면 설정에서 켜세요</Link>}
        <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
          <Chip active={onlyLiked} onClick={() => setOnlyLiked((v) => !v)}><Heart className="mr-1 inline h-3.5 w-3.5" />좋아요만</Chip>
          <Select aria-label="정렬" value={sort} onChange={(e) => setSort(e.target.value)} className="w-auto rounded-full py-2">
            {SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </Select>
        </div>
      </Card>

      {notice && <Notice role="status">{notice}</Notice>}
      {(data.items ?? []).some((i) => i.given_hanja && i.gate.official_hanja === "unknown") && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><Info className="h-3.5 w-3.5" />
          한자가 인명용으로 허용되는지는 아직 공식 자료로 확인하지 않았어요. 마음에 드는 이름은 &lsquo;최종 결정&rsquo;에서 확인할 수 있어요.</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((i) => (
          <CandidateCard key={i.id} item={i} selected={selected.includes(i.id!)}
                         onSelect={(v) => setSelected((s) => v ? [...s, i.id!].slice(0, 10) : s.filter((x) => x !== i.id))}
                         onReact={(r) => react(i.id!, r)} />
        ))}
      </div>
      {items.length === 0 && <Card className="text-center text-sm text-muted-foreground">{onlyLiked ? "아직 좋아요 한 이름이 없어요." : "후보가 없어요. '후보 더 받기'를 눌러 보세요."}</Card>}

      <div className="grid gap-3 md:grid-cols-2">
        <Card className="space-y-2 p-4">
          <p className="text-sm font-medium">직접 넣어 보기</p>
          <div className="flex gap-2">
            <Input aria-label="이름(성 제외)" placeholder="이름 (예: 지아)" value={manual.hangul} onChange={(e) => setManual((m) => ({ ...m, hangul: e.target.value }))} />
            <Input aria-label="한자 (선택)" placeholder="한자 (선택)" value={manual.hanja} onChange={(e) => setManual((m) => ({ ...m, hanja: e.target.value }))} />
            <Button variant="soft" size="icon" aria-label="추가" disabled={!manual.hangul} onClick={addManual}><Plus className="h-4 w-4" /></Button>
          </div>
        </Card>
        {warnings.length > 0 && (
          <Card className="p-4">
            <Details summary={`안내 ${warnings.length}개`}>
              <ul className="space-y-1 text-xs text-muted-foreground">{warnings.map((w) => <li key={w.code} className="flex gap-1.5"><Info className="mt-0.5 h-3 w-3 shrink-0" />{w.message}</li>)}</ul>
            </Details>
          </Card>
        )}
      </div>

      {consent && <ConsentDialog preview={consent} onCancel={() => setConsent(null)} onConfirm={() => { setConsent(null); generate(true); }} />}
    </div>
  );
}
