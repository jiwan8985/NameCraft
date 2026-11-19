"use client";

import { useState } from "react";
import { AnalysisSections } from "@/components/naming/analysis-sections";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Field, Input, Notice } from "@/components/ui/form";
import { postJson } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */

/** /names/analyze — 직접 이름 입력 분석 + 한글 이름 → 한자 역검색 (기획서 §8.2) */
export function NameAnalyzer() {
  const [form, setForm] = useState({ sh: "", sx: "", gh: "", gx: "" });
  const [analysis, setAnalysis] = useState<any>(null);
  const [rs, setRs] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function analyze() {
    setError(null);
    const r = await postJson<any>("names/analyze", { surname_hangul: form.sh, surname_hanja: form.sx || null,
                                                    given_hangul: form.gh, given_hanja: form.gx || null });
    if (r.ok) setAnalysis(r.data); else setError(r.error.message);
  }
  async function reverse() {
    setError(null);
    const r = await postJson<any>("names/reverse-search", { given_hangul: form.gh, surname_hanja: form.sx || null, limit: 20 });
    if (r.ok) setRs(r.data); else setError(r.error.message);
  }
  const combos = rs ? [...rs.combinations.passed, ...rs.combinations.on_hold] : [];

  return (
    <div className="space-y-4">
      <Card className="grid gap-3 sm:grid-cols-4">
        <Field label="성 (한글)" htmlFor="sh"><Input id="sh" value={form.sh} onChange={set("sh")} /></Field>
        <Field label="성 한자" htmlFor="sx"><Input id="sx" value={form.sx} onChange={set("sx")} /></Field>
        <Field label="이름 (한글)" htmlFor="gh"><Input id="gh" value={form.gh} onChange={set("gh")} /></Field>
        <Field label="이름 한자 (선택)" htmlFor="gx"><Input id="gx" value={form.gx} onChange={set("gx")} /></Field>
        <div className="flex gap-2 sm:col-span-4">
          <Button disabled={!form.sh || !form.gh} onClick={analyze}>이름 분석</Button>
          <Button variant="outline" disabled={!form.gh} onClick={reverse}>한자 조합 찾기</Button>
        </div>
      </Card>
      {error && <Notice tone="danger" role="alert">{error}</Notice>}
      {rs && (
        <Card className="space-y-2">
          <CardTitle>&lsquo;{rs.given_hangul}&rsquo; 한자 조합</CardTitle>
          {rs.impossible_syllables.length > 0 && <Notice tone="warn">인명용 독음 한자가 없는 음절: {rs.impossible_syllables.join("")} — 한글 이름으로 쓸 수 있습니다.</Notice>}
          {rs.counts && <p className="text-xs text-muted-foreground">공식 확인 {rs.counts.passed} · 보류(공식 자료 미적재) {rs.counts.on_hold} · 차단 {rs.counts.rejected} / 전체 {rs.total_combinations}</p>}
          <table className="w-full text-sm">
            <caption className="sr-only">한자 조합 정렬 결과</caption>
            <thead className="text-left text-xs text-muted-foreground"><tr><th>한자</th><th>정렬 점수</th><th>교육용</th><th>뜻 주의 없음</th><th>81수리</th><th>음양</th><th>상태</th></tr></thead>
            <tbody>
              {combos.map((c: any) => (
                <tr key={c.hanja} className="border-t border-border">
                  <td className="py-1"><button className="hover:underline" onClick={() => setForm((f) => ({ ...f, gx: c.hanja }))}>{c.hanja}</button></td>
                  <td className="tabular-nums">{c.optimization_score ?? "N/A"}</td>
                  <td className="tabular-nums">{c.components.common_hanja}</td>
                  <td className="tabular-nums">{c.components.no_meaning_caution}</td>
                  <td>{c.traditional ? Object.values(c.traditional.luck81).join("·") : "N/A"}</td>
                  <td>{c.traditional ? c.traditional.yinyang.join("") : "N/A"}</td>
                  <td className="text-xs">{c.bucket === "passed" ? "공식 확인" : "보류"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-muted-foreground">정렬 점수는 조합을 고르는 보조 지표입니다. 한자를 누르면 분석 칸에 들어갑니다.</p>
        </Card>
      )}
      {analysis && <AnalysisSections analysis={analysis} />}
    </div>
  );
}
