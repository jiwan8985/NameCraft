import { CategoryBars } from "@/components/score";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { CATEGORY_ORDER, type RankedItem } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Analysis = any;

const GYEOK = [["won", "원격"], ["hyeong", "형격"], ["i", "이격"], ["jeong", "정격"]] as const;

/** 이름 분석 결과 — 모든 점수·판정에 근거와 성격(계산/전통 해석/후보/주관)을 함께 표시 (Phase 8 게이트) */
export function AnalysisSections({ analysis, ranking }: { analysis: Analysis; ranking?: RankedItem }) {
  const ph = analysis.phonetics;
  const num = analysis.numerology;
  return (
    <div className="space-y-4">
      {ranking && (
        <Card className="space-y-3">
          <CardTitle>항목별 점수와 근거</CardTitle>
          <CategoryBars categories={ranking.categories} />
          <table className="w-full text-sm">
            <caption className="sr-only">항목별 점수 근거</caption>
            <thead className="text-left text-xs text-muted-foreground">
              <tr><th className="py-1">항목</th><th>점수</th><th>비중(실제)</th><th>성격</th><th>근거</th></tr>
            </thead>
            <tbody>
              {CATEGORY_ORDER.map((k) => {
                const c = ranking.categories[k];
                return (
                  <tr key={k} className="border-t border-border align-top">
                    <th scope="row" className="py-1 pr-2 text-left font-normal">{c.label}</th>
                    <td className="tabular-nums">{c.score ?? "N/A"}</td>
                    <td className="tabular-nums">{Math.round(c.weight * 100)}% ({Math.round(c.effective_weight * 100)}%)</td>
                    <td className="text-xs">{c.nature}</td>
                    <td className="text-xs text-muted-foreground">{c.basis}{c.disputed?.length ? ` · 학파 이견: ${c.disputed.join(", ")}` : ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="text-xs text-muted-foreground">
            종합 {ranking.overall ?? "N/A"} = 사용 가능한 항목의 가중 평균. 공식 한자 판정은 점수와 별도: {ranking.gate.official_hanja}.
            신뢰도 — 데이터: {ranking.confidence.data_verification}, 재현 가능: {ranking.confidence.reproducible ? "예" : "아니오"},
            음령오행 학파 일치 {ranking.confidence.school_agreement.agree_count}/{ranking.confidence.school_agreement.total}
            ({ranking.confidence.school_agreement.note}), AI 주관 평가: {ranking.confidence.ai_subjective ? "있음" : "없음"}
          </p>
        </Card>
      )}

      <Card className="space-y-2">
        <div className="flex items-center justify-between"><CardTitle>발음</CardTitle><StatusBadge status="calculated" /></div>
        <p className="text-sm">표기 <b>{ph.pronunciation.written}</b> → 발음 <b>[{ph.pronunciation.pronounced}]</b></p>
        {ph.pronunciation.rules.length > 0 && (
          <ul className="list-disc pl-5 text-xs text-muted-foreground">
            {ph.pronunciation.rules.map((r: any, i: number) => <li key={i}>{r.rule_id}: {r.description}</li>)}
          </ul>
        )}
        <p className="text-sm">발음 편의 점수 {ph.ease_score} <StatusBadge status="subjective" /></p>
        {ph.ease_rubric.deductions.length > 0 && (
          <ul className="list-disc pl-5 text-xs text-muted-foreground">
            {ph.ease_rubric.deductions.map((d: any) => <li key={d.feature}>−{d.points}: {d.description} ({d.count})</li>)}
          </ul>
        )}
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center justify-between"><CardTitle>부정 연상 후보</CardTitle><StatusBadge status="candidate" /></div>
        {analysis.caution.candidates.length === 0
          ? <p className="text-sm">목록과 일치하는 표현이 없습니다.</p>
          : <ul className="list-disc pl-5 text-sm">{analysis.caution.candidates.map((c: any) => (
              <li key={c.word}>&lsquo;{c.word}&rsquo; ({c.category}, {c.match === "exact" ? "정확 일치" : "비슷한 소리"})</li>))}</ul>}
        <CardDescription>{analysis.caution.note}</CardDescription>
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center justify-between"><CardTitle>한자 뜻</CardTitle><StatusBadge status={analysis.meaning.status === "not_applicable" ? "not_applicable" : "candidate"} /></div>
        {analysis.meaning.characters ? (
          <ul className="space-y-1 text-sm">
            {analysis.meaning.characters.map((c: any) => (
              <li key={c.hanja}><b>{c.hanja}</b> — {c.definition_en ?? "풀이 없음"} <span className="text-xs text-muted-foreground">(Unihan 영어 풀이)</span>
                {c.caution_keywords.length > 0 && <span className="ml-1 text-xs text-warn">주의 키워드: {c.caution_keywords.join(", ")}</span>}</li>
            ))}
          </ul>
        ) : <p className="text-sm">{analysis.meaning.note}</p>}
        <CardDescription>한국어 뜻·의미 조합 평가: 자료 없음</CardDescription>
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center justify-between"><CardTitle>전통 수리·오행</CardTitle><StatusBadge status="traditional" /></div>
        {num.applicability.numerology !== "applicable" ? (
          <p className="text-sm">{num.applicability.reason}</p>
        ) : (
          <>
            <table className="w-full text-sm">
              <caption className="sr-only">원형이정 4격</caption>
              <thead className="text-left text-xs text-muted-foreground"><tr><th>격</th><th>수</th><th>수리오행</th><th>81수리</th></tr></thead>
              <tbody>
                {GYEOK.map(([k, l]) => (
                  <tr key={k} className="border-t border-border">
                    <th scope="row" className="py-1 text-left font-normal">{l}</th>
                    <td className="tabular-nums">{num.calc.four_gyeok[k].value}</td>
                    <td>{num.calc.four_gyeok[k].element}</td>
                    <td>{num.trad.luck81[k].label}{num.trad.luck81[k].disputed ? " (학파 이견)" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-muted-foreground">
              획수({num.stroke_system === "original" ? "원획" : "필획"}): {num.characters.map((c: any) => `${c.hanja}${c.strokes}`).join(" · ")} ·
              음양 {num.calc.yinyang_pattern.join("")} ({num.trad.yinyang.value})
            </p>
          </>
        )}
        <p className="text-xs text-muted-foreground">
          음령오행({num.eumryeong.school}): {num.eumryeong.elements.join(" ")} · 다른 학파: {num.eumryeong.by_school["hunmin-haerye"].elements.join(" ")}
        </p>
        <CardDescription>전통 해석이며 과학적 근거가 없습니다. 이름이 건강·성공·운명을 결정하지 않습니다.</CardDescription>
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center justify-between"><CardTitle>사용성·로마자</CardTitle><StatusBadge status="subjective" /></div>
        {analysis.usability.notes.length === 0 ? <p className="text-sm">특별한 참고 사항이 없습니다.</p>
          : <ul className="list-disc pl-5 text-sm">{analysis.usability.notes.map((n: any) => <li key={n.code}>{n.message}</li>)}</ul>}
        <p className="text-sm">로마자(RR): {analysis.romanization.surname_rr} {analysis.romanization.given_rr}
          {analysis.romanization.surname_customary_examples.length > 0 && <span className="text-xs text-muted-foreground"> · 성씨 관용 표기 예: {analysis.romanization.surname_customary_examples.join(", ")}</span>}</p>
        {analysis.romanization.english_pitfalls.items.length > 0 && (
          <p className="text-xs text-warn">영어권 확인: {analysis.romanization.english_pitfalls.items.map((p: any) => `${p.text}(${p.note})`).join(", ")}</p>
        )}
        <CardDescription>{analysis.romanization.note}</CardDescription>
      </Card>
    </div>
  );
}
