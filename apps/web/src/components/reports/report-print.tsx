"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AnalysisSections } from "@/components/naming/analysis-sections";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";
import { CATEGORY_ORDER, CATEGORY_SHORT } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
const TITLE: Record<string, string> = { project_summary: "작명 프로젝트 요약 보고서", name_detail: "이름 상세 보고서", comparison: "후보 비교 보고서" };

function RankTable({ items }: { items: any[] }) {
  return (
    <table className="w-full border-collapse text-xs">
      <thead><tr className="border-b border-border text-left">{["이름", "한자", "종합", ...CATEGORY_ORDER.map((k) => CATEGORY_SHORT[k]), "공식 한자"].map((h) => <th key={h} className="py-1 pr-2">{h}</th>)}</tr></thead>
      <tbody>{items.map((i) => (
        <tr key={i.id ?? i.full_hangul} className="border-b border-border">
          <td className="py-1 pr-2">{i.full_hangul}</td><td>{i.given_hanja ?? "—"}</td><td>{i.overall ?? "N/A"}</td>
          {CATEGORY_ORDER.map((k) => <td key={k}>{i.categories[k].score ?? "N/A"}</td>)}
          <td>{i.given_hanja ? i.gate.official_hanja : "한글 이름"}</td></tr>))}</tbody>
    </table>
  );
}

/** 인쇄용 보고서 — 브라우저 인쇄 → 'PDF로 저장' (D-043) */
export function ReportPrint() {
  const id = useSearchParams().get("id");
  const [r, setR] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (id) apiFetch<any>(`reports/${id}`).then((x) => x.ok ? setR(x.data) : setErr(x.error.message)); }, [id]);
  if (err) return <Notice tone="danger">{err}</Notice>;
  if (!r) return <p className="text-sm text-muted-foreground">불러오는 중…</p>;
  const s = r.snapshot;
  const c = s.conditions;
  return (
    <article className="mx-auto max-w-4xl space-y-5 bg-white p-6 text-black print:p-0">
      <div className="flex items-start justify-between print:hidden">
        <p className="text-sm text-gray-600">인쇄 대화상자에서 &lsquo;PDF로 저장&rsquo;을 고르면 PDF 파일이 됩니다.</p>
        <Button onClick={() => window.print()}>인쇄 / PDF로 저장</Button>
      </div>
      <header className="border-b border-gray-300 pb-3">
        <h1 className="text-2xl font-bold">{TITLE[r.kind]}</h1>
        <p className="text-sm">{c.project.title} · 생성 {r.created_at.slice(0, 16)} · 보고서 ID {r.id.slice(0, 8)}</p>
      </header>
      <section>
        <h2 className="mb-1 font-semibold">입력 조건</h2>
        <ul className="text-sm">
          <li>성씨: {c.project.surname_hangul}{c.project.surname_hanja ? ` (${c.project.surname_hanja})` : ""} · 성별 선호: {c.project.sex}</li>
          <li>출생정보: {c.birth ? `${c.birth.kind_label} — ${c.birth.calendar === "lunar" ? "음력" : "양력"} ${c.birth.date} ${c.birth.time ?? (c.birth.time_range ? c.birth.time_range.join("~") : "시간 미정")}${c.birth.day_window ? ` (±${c.birth.day_window}일)` : ""}` : "입력 안 함"}</li>
          <li>적용 학파·옵션: 획수 {c.school_options.stroke_system === "original" ? "원획" : "필획"}, 외자 가수 {c.school_options.single_name_virtual_stroke}, 음령오행 {c.school_options.eumryeong_school}, 사주 해석 {c.school_options.use_saju ? c.school_options.saju_interpretation : "사용 안 함"}{c.school_options.true_solar_time ? `, 시각 기준 ${c.school_options.true_solar_time}, 자시 ${c.school_options.zi_convention}` : ""}</li>
          <li>공식 인명용 한자 자료: {s.official_basis.official_data_loaded ? `확인일 ${s.official_basis.checked_at?.slice(0, 10)}, 고시 ${s.official_basis.effective_date ?? "미상"}` : "미적재 — 최종 공식 재확인 필요"}</li>
          <li>계산 버전: 앱 {r.versions.app} · 랭킹 {r.versions.ranking} · 수리 규칙 {r.versions.numerology_rule} · 만세력 {r.versions.calendar_engine} · 데이터 {r.versions.data_releases.join(", ")}</li>
        </ul>
      </section>
      {s.ranking && <section><h2 className="mb-1 font-semibold">후보 순위 (상위 {s.ranking.items.length})</h2><RankTable items={s.ranking.items} /></section>}
      {s.comparison && <section><h2 className="mb-1 font-semibold">비교</h2><RankTable items={s.comparison.items} /></section>}
      {s.scenario && (
        <section><h2 className="mb-1 font-semibold">출생 시나리오</h2>
          <p className="text-sm">시나리오 {s.scenario.scenario_count}개 · 서로 다른 명식 {s.scenario.distinct_charts}개 · 바뀌는 기둥 {s.scenario.varying_pillars.join(", ") || "없음"}</p>
          <p className="text-xs">{s.scenario.notes.join(" ")}</p></section>
      )}
      {s.decision && (
        <section><h2 className="mb-1 font-semibold">최종 결정</h2>
          <p className="text-sm">{s.decision.name} {s.decision.hanja ?? ""} — {s.decision.reason} ({s.decision.decided_at.slice(0, 10)})</p>
          {s.finalize_check && <p className="text-sm">출생신고 준비 점검: <b>{s.finalize_check.overall_label}</b></p>}</section>
      )}
      {s.detail && <section><h2 className="mb-1 font-semibold">{s.detail.analysis.name.full_hangul} 상세</h2><AnalysisSections analysis={s.detail.analysis} ranking={s.detail.ranking} /></section>}
      <section className="border-t border-gray-300 pt-3">
        <h2 className="mb-1 font-semibold">해석 한계</h2>
        <ul className="list-disc pl-5 text-xs">{s.limitations.map((x: string) => <li key={x}>{x}</li>)}</ul>
      </section>
    </article>
  );
}
