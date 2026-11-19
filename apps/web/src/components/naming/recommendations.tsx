"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ConsentDialog, type ConsentPreview } from "@/components/consent-dialog";
import { CategoryBars } from "@/components/score";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Input, Notice, Select } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";
import type { Project, RankedItem, Warning } from "@/lib/types";

const SORTS = [
  ["overall", "종합"], ["phonetic", "발음·어감"], ["meaning", "의미"], ["numerology", "전통 수리"],
  ["usability", "현대적 사용성"], ["preference", "내 선호"],
] as const;
const PROVIDERS = [
  ["none", "AI 사용 안 함(규칙 기반)"], ["auto", "자동(켜 둔 AI만)"], ["ollama", "Ollama(로컬)"],
  ["claude_code", "Claude Code(구독)"], ["antigravity", "Antigravity(구독)"],
] as const;
const GATE_LABEL = { pass: "official", unknown: "unverified", fail: "not_listed" } as const;
const SOURCE_LABEL: Record<string, string> = { rule_based: "규칙 기반", data_based: "예시 기반", ai_based: "AI 제안", user: "직접 추가" };

type ListData = { items: RankedItem[]; weights_normalized: Record<string, number>; ranking_version: string };

export function CandidateCard({ item, selected, onSelect, onReact }: {
  item: RankedItem; selected: boolean; onSelect: (v: boolean) => void; onReact: (r: "like" | "dislike" | "hold") => void;
}) {
  return (
    <Card className="space-y-3" aria-label={item.full_hangul}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <CardTitle className="text-lg">
            <Link href={`/names/${item.id}`} className="hover:underline">{item.full_hangul}</Link>
          </CardTitle>
          <CardDescription>{item.given_hanja ? `${item.given_hanja}` : "한자 없음"} · {SOURCE_LABEL[item.source ?? ""] ?? item.source}</CardDescription>
        </div>
        <div className="text-right">
          <p className="text-2xl font-semibold tabular-nums">{item.overall ?? "N/A"}</p>
          <p className="text-xs text-muted-foreground">종합(선별 참고)</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-1">
        <StatusBadge status={item.given_hanja ? GATE_LABEL[item.gate.official_hanja] : "hangul_name"} />
        {item.gate.official_hanja === "unknown" && <span className="text-xs text-muted-foreground">공식 한자 확인 전</span>}
        {item.gate.caution === "review" && <StatusBadge status="review" />}
        {item.incomplete.length > 0 && <span className="text-xs text-muted-foreground">N/A: {item.incomplete.length}개 항목</span>}
      </div>
      <CategoryBars categories={item.categories} />
      {item.ai_reason && <p className="text-xs text-muted-foreground">AI 의견(주관): {item.ai_reason}</p>}
      <div className="flex flex-wrap items-center gap-2">
        {([["like", "좋아요"], ["hold", "보류"], ["dislike", "싫어요"]] as const).map(([r, label]) => (
          <Button key={r} size="sm" variant={item.reaction === r ? "default" : "outline"} aria-pressed={item.reaction === r}
                  onClick={() => onReact(r)}>{label}</Button>
        ))}
        <label className="ml-auto inline-flex items-center gap-1 text-xs">
          <input type="checkbox" checked={selected} onChange={(e) => onSelect(e.target.checked)} /> 비교
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
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState("none");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [consent, setConsent] = useState<ConsentPreview | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [manual, setManual] = useState({ hangul: "", hanja: "" });

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
    setNotice(`${r.data.saved.length}개 후보를 추가했습니다 (생성: ${r.data.provider_used}${r.data.fallback_reason ? ", AI 사용 불가로 규칙 기반 대체" : ""}).`);
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

  const items = useMemo(() => (data?.items ?? []).filter((i) =>
    filter === "all" ? true : filter === "liked" ? i.reaction === "like" : filter === "official" ? i.gate.official_hanja === "pass"
      : filter === "caution" ? i.gate.caution === "review" : true), [data, filter]);

  if (error) return <Notice tone="danger" role="alert">{error}</Notice>;
  if (!project || !data) return <p aria-busy="true" className="text-sm text-muted-foreground">불러오는 중…</p>;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">{project.title}</h1>
          <p className="text-sm text-muted-foreground">성씨 {project.surname_hangul}{project.surname_hanja ? `(${project.surname_hanja})` : ""} · 후보 {data.items.length}개 · 랭킹 {data.ranking_version}</p>
        </div>
        {selected.length >= 2 && (
          <Link href={`/compare?project=${projectId}&ids=${selected.join(",")}`} className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground">
            선택한 {selected.length}개 비교
          </Link>
        )}
      </header>

      {warnings.map((w) => <Notice key={w.code} tone="warn">{w.message}</Notice>)}
      {notice && <Notice role="status">{notice}</Notice>}

      <Card className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <Field label="정렬" htmlFor="sort">
          <Select id="sort" value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </Select>
        </Field>
        <Field label="보기" htmlFor="filter">
          <Select id="filter" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">전체</option><option value="liked">좋아요</option>
            <option value="official">공식 한자 확인</option><option value="caution">검토 필요</option>
          </Select>
        </Field>
        <p className="text-xs text-muted-foreground">싫어요 한 후보는 목록·재추천에서 빠집니다(상세에서 복구).</p>
      </Card>

      <Card className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
        <Field label="후보 더 만들기 — 생성 방식" htmlFor="provider" hint="AI 결과도 서버가 한자·발음·조건을 다시 검증합니다.">
          <Select id="provider" value={provider} onChange={(e) => setProvider(e.target.value)}>
            {PROVIDERS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </Select>
        </Field>
        <Button disabled={busy} onClick={() => generate(false)}>{busy ? "생성 중…" : "후보 생성"}</Button>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((i) => (
          <CandidateCard key={i.id} item={i} selected={selected.includes(i.id!)}
                         onSelect={(v) => setSelected((s) => v ? [...s, i.id!].slice(0, 10) : s.filter((x) => x !== i.id))}
                         onReact={(r) => react(i.id!, r)} />
        ))}
      </div>
      {items.length === 0 && <p className="text-sm text-muted-foreground">표시할 후보가 없습니다.</p>}

      <Card className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <Field label="직접 추가 — 이름(성 제외)" htmlFor="m-hangul">
          <Input id="m-hangul" value={manual.hangul} onChange={(e) => setManual((m) => ({ ...m, hangul: e.target.value }))} />
        </Field>
        <Field label="한자 (선택)" htmlFor="m-hanja">
          <Input id="m-hanja" value={manual.hanja} onChange={(e) => setManual((m) => ({ ...m, hanja: e.target.value }))} />
        </Field>
        <Button variant="outline" disabled={!manual.hangul} onClick={addManual}>추가</Button>
      </Card>

      {consent && <ConsentDialog preview={consent} onCancel={() => setConsent(null)}
                                 onConfirm={() => { setConsent(null); generate(true); }} />}
    </div>
  );
}
