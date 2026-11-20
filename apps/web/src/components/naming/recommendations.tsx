"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, Heart, Info, Loader2, Plus, Sparkles, X } from "lucide-react";
import { ProjectNav } from "@/components/collab/use-project";
import { AIPicker, useLocalAI, type NamingMethod } from "@/components/ai-picker";
import { CategoryBars } from "@/components/score";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Chip, Details, Input, Notice, Select } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";
import type { Project, RankedItem, Warning } from "@/lib/types";
import { cn } from "@/lib/utils";

const SORTS = [["recommended", "추천 순서"], ["overall", "점수순"], ["phonetic", "발음"], ["meaning", "의미"], ["numerology", "전통 수리"], ["usability", "쓰기 편함"], ["preference", "내 취향"]] as const;

type ListData = { items: RankedItem[]; weights_normalized: Record<string, number>; ranking_version: string };

/** AI 설명 앞의 '瑞 상서로울 서, 雅 맑을 아.' 훈음 나열은 카드 위에 이미 보이므로 뺀다. */
export function reasonWithoutMeanings(reason: string, hasHanja: boolean) {
  if (!hasHanja) return reason;
  const out = reason.replace(/^(\s*[\u3400-\u9fff\uf900-\ufaff]\s*[(（]?[가-힣 ]{1,14}[)）]?\s*[,·、]?\s*)+[.。]\s*/, "");
  return out.length > 0 ? out : reason;
}

export function CandidateCard({ item, selected, onSelect, onReact }: {
  item: RankedItem; selected: boolean; onSelect: (v: boolean) => void; onReact: (r: "like" | "dislike" | "hold") => void;
}) {
  const liked = item.reaction === "like";
  const ai = item.source === "ai_based";
  const sajuScore = item.categories.saju?.score;
  return (
    <Card aria-label={item.full_hangul} className={cn("flex flex-col gap-3 transition hover:shadow-md", liked && "ring-2 ring-primary/50")}>
      <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
        {ai && <span className="inline-flex items-center gap-1 rounded-full bg-primary-soft px-2 py-0.5 font-medium text-primary"><Sparkles className="h-3 w-3" />{item.provider_id === "ollama" ? "Ollama" : "AI"} 추천</span>}
        {item.trend && <span className="rounded-full bg-ok-soft px-2 py-0.5 font-medium text-ok">요즘 인기</span>}
        {(item.native || (!item.given_hanja && !ai)) && <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">{item.native ? "순우리말" : "한글 이름"}</span>}
        {item.given_hanja && item.gate.official_hanja === "fail" && <span className="rounded-full bg-danger-soft px-2 py-0.5 text-danger">인명용 아님</span>}
        {item.gate.caution === "review" && <span className="rounded-full bg-warn-soft px-2 py-0.5 text-warn">발음 검토</span>}
        <span className="ml-auto text-xs tabular-nums text-muted-foreground" title="종합 점수">{item.overall === null ? "" : `${Math.round(item.overall)}점`}</span>
      </div>
      <Link href={`/names/${item.id}`} className="group">
        <p className="text-3xl font-bold tracking-wider group-hover:text-primary">{item.full_hangul}</p>
        {item.given_hanja && (
          <p className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-sm">
            {(item.hanja_meanings ?? [...item.given_hanja].map((c) => ({ char: c, meaning: null }))).map((m, i) => (
              <span key={i} className="inline-flex items-baseline gap-1">
                <span className="text-lg font-medium">{m.char}</span>
                {m.meaning && <span className="text-xs text-muted-foreground">{m.meaning}</span>}
              </span>
            ))}
          </p>
        )}
      </Link>
      {item.ai_reason && <p className="text-sm leading-relaxed text-muted-foreground">{reasonWithoutMeanings(item.ai_reason, !!item.given_hanja)}</p>}
      {typeof sajuScore === "number" && (
        <p className="text-xs font-medium text-primary">사주 참고 {Math.round(sajuScore)}점</p>
      )}
      <Details summary="평가 근거 보기">
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
  const loadSequence = useRef(0);
  const [data, setData] = useState<ListData | null>(null);
  const [warnings, setWarnings] = useState<Warning[]>([]);
  const [sort, setSort] = useState("recommended");
  const [onlyLiked, setOnlyLiked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [choice, setProvider] = useState<NamingMethod | null>(null);
  const localAvailable = useLocalAI();
  const who = choice ?? (localAvailable ? "ollama" : "none");
  const [showPicker, setShowPicker] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [manual, setManual] = useState({ hangul: "", hanja: "" });
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("sort") === "saju") setSort("saju");
    const note = params.get("note");
    if (note === "ai_fallback") setNotice("AI 가 응답하지 않아 이름 사전에서 골랐어요. 아래 '더 받기'로 다시 시도해 보세요.");
    if (note === "ai_error") setNotice("이름을 받지 못했어요. 아래 '더 받기'로 다시 시도해 보세요.");
  }, []);

  const load = useCallback(async () => {
    const request = ++loadSequence.current;
    const [p, c] = await Promise.all([apiFetch<Project>(`projects/${projectId}`),
                                      apiFetch<ListData>(`projects/${projectId}/candidates?sort=${sort}`)]);
    if (request !== loadSequence.current) return;
    if (!p.ok) return setError(p.error.message);
    if (!c.ok) return setError(c.error.message);
    setError(null);
    setProject(p.data);
    setData(c.data);
    setWarnings(c.warnings);
  }, [projectId, sort]);
  useEffect(() => { load(); }, [load]);

  async function generate() {
    setBusy(true);
    setNotice(null);
    const r = await postJson<{ provider_used: string; saved: unknown[] }>(
      `projects/${projectId}/candidates/generate`, { provider: who, ...(who === "ollama" ? { local_only: true, count: 5 } : {}) });
    setBusy(false);
    if (!r.ok) return setNotice(r.error.message);
    const by = r.data.provider_used === "ollama" ? "Ollama" : "이름 사전";
    if (who === "ollama" && r.data.provider_used !== "ollama") setNotice("로컬 AI가 이름을 만들지 못해 이름 사전에서 후보를 찾았어요.");
    else if (r.data.saved.length === 0) setNotice(who === "ollama" ? "새로운 이름을 받지 못했어요." : "이름 사전의 조건에 맞는 이름은 모두 보여 드렸어요.");
    else setNotice(`${by}에서 새 이름 ${r.data.saved.length}개를 받았어요.`);
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
  const groups = useMemo(() => {
    if (sort !== "recommended") return items.length ? [{ title: "", items }] : [];
    const aiItems = items.filter((i) => i.source === "ai_based");
    const rest = items.filter((i) => i.source !== "ai_based");
    return [{ title: "AI 가 고른 이름", items: aiItems }, { title: aiItems.length ? "이름 사전에서 고른 이름" : "", items: rest }].filter((g) => g.items.length);
  }, [items, sort]);
  const likedCount = (data?.items ?? []).filter((i) => i.reaction === "like").length;

  if (error) return <Notice tone="danger" role="alert">{error}</Notice>;
  if (!project || !data) return <p aria-busy="true" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…</p>;

  return (
    <div className={cn("space-y-5", selected.length > 0 && "pb-20")}>
      <header className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{project.title}</h1>
            <p className="text-sm text-muted-foreground">후보 {data.items.length}개 · 좋아요 {likedCount}개</p>
          </div>
        </div>
        <ProjectNav projectId={projectId} />
      </header>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-primary-soft p-4">
        <div className="flex items-start gap-3">
          <CalendarDays className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
          <div>
            <p className="font-semibold">출생정보로 사주 살펴보기</p>
            <p className="mt-1 text-sm text-muted-foreground">예정일이나 시간 범위로 살펴보고, 출생 후 실제 정보로 다시 비교할 수 있어요.</p>
          </div>
        </div>
        <Link href={`/scenario?project=${projectId}`} className={buttonVariants({ variant: "outline" })}>출생정보 열기</Link>
      </div>

      <Card className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-2 [&>*]:min-w-0">
          <Button disabled={busy || (choice === null && localAvailable === null)} onClick={generate}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {busy ? "고르는 중…" : who === "ollama" ? "AI로 더 받기" : "이름 사전에서 더 받기"}
          </Button>
          <Button variant="ghost" size="sm" aria-expanded={showPicker} onClick={() => setShowPicker((v) => !v)}>추천 방법 선택</Button>
          <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
            <Chip active={onlyLiked} onClick={() => setOnlyLiked((v) => !v)}><Heart className="mr-1 inline h-3.5 w-3.5" />좋아요만</Chip>
            <Select aria-label="정렬" value={sort} onChange={(e) => setSort(e.target.value)} className="w-auto rounded-full py-2">
              {SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              {!!project.preferences.use_saju && <option value="saju">사주 반영 점수</option>}
            </Select>
          </div>
        </div>
        {showPicker && <AIPicker value={who} localAvailable={localAvailable} onChange={(v) => { setProvider(v); setShowPicker(false); }} />}
      </Card>

      {notice && <Notice role="status">{notice}</Notice>}
      {(data.items ?? []).some((i) => i.given_hanja && i.gate.official_hanja === "unknown") && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><Info className="h-3.5 w-3.5" />
          공식 인명용 한자 여부가 아직 확인되지 않은 후보가 있어요.</p>
      )}

      {items.length > 0 && <p className="text-sm text-muted-foreground">마음에 드는 이름에 좋아요를 누르거나, 이름 두 개 이상에 비교를 체크해 보세요.</p>}

      {groups.map((g) => (
        <section key={g.title || "rest"} className="space-y-3">
          {g.title && <h2 className="text-sm font-semibold text-muted-foreground">{g.title} <span className="font-normal">{g.items.length}</span></h2>}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {g.items.map((i) => (
              <CandidateCard key={i.id} item={i} selected={selected.includes(i.id!)}
                             onSelect={(v) => setSelected((s) => v ? [...s, i.id!].slice(0, 10) : s.filter((x) => x !== i.id))}
                             onReact={(r) => react(i.id!, r)} />
            ))}
          </div>
        </section>
      ))}
      {items.length === 0 && <Card className="text-center text-sm text-muted-foreground">{onlyLiked ? "아직 좋아요 한 이름이 없어요." : "아직 이름이 없어요. 위의 '더 받기'를 눌러 보세요."}</Card>}

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

      {selected.length > 0 && (
        <div className="fixed inset-x-4 bottom-4 z-30 mx-auto flex max-w-lg flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-card p-3 shadow-lg">
          <p role="status" className="text-sm text-muted-foreground">비교할 이름 {selected.length}개 선택{selected.length === 1 ? " · 1개 더 골라 주세요" : ""}</p>
          <div className="flex flex-wrap gap-1.5">
            <Button size="sm" variant="ghost" onClick={() => setSelected([])}>선택 해제</Button>
            {selected.length >= 2 && (
              <Link href={`/compare?project=${projectId}&ids=${selected.join(",")}`} className={buttonVariants({ size: "sm" })}>이름 비교</Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
