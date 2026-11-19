import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { ConsentDialog } from "@/components/consent-dialog";
import { AnalysisSections } from "@/components/naming/analysis-sections";
import { CandidateCard } from "@/components/naming/recommendations";
import { RadarChart, ScoreBar } from "@/components/score";
import type { RankedItem } from "@/lib/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

const cat = (score: number | null, label: string) => ({ score, basis: `${label} 근거`, label, nature: "subjective", weight: 0.2, effective_weight: score === null ? 0 : 0.25 });
const item: RankedItem = {
  id: "c1", given_hangul: "지아", given_hanja: "智雅", full_hangul: "심지아", source: "ai_based", overall: 81.2,
  gate: { official_hanja: "unknown", caution: "review" },
  categories: { phonetic: cat(93, "발음·어감"), meaning: cat(70, "이름 의미"), saju: cat(null, "전통 사주·오행 해석"),
                numerology: cat(80, "전통 획수·수리 해석"), usability: cat(100, "현대적 사용성"), preference: cat(null, "희소성·개인 선호") },
  incomplete: ["saju", "preference"],
  confidence: { data_verification: "unverified", reproducible: true, school_agreement: { agree_count: 2, total: 3, note: "일치도는 정확성 아님" }, ai_subjective: true },
  ai_reason: "부르기 편함", reaction: "like",
};

describe("CandidateCard", () => {
  it("shows N/A (not 0), gate status, caution badge, source, AI opinion label", () => {
    const onReact = vi.fn();
    render(<CandidateCard item={item} selected={false} onSelect={() => {}} onReact={onReact} />);
    expect(screen.getAllByText("N/A")).toHaveLength(2);
    expect(screen.getByText("미확인")).toBeInTheDocument();
    expect(screen.getByText("공식 한자 확인 전")).toBeInTheDocument();
    expect(screen.getByText("검토 권장")).toBeInTheDocument();
    expect(screen.getByText(/AI 제안/)).toBeInTheDocument();
    expect(screen.getByText(/AI 의견\(주관\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "좋아요" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "싫어요" }));
    expect(onReact).toHaveBeenCalledWith("dislike");
  });
  it("hangul-only names show hangul badge instead of hanja gate", () => {
    render(<CandidateCard item={{ ...item, given_hanja: null, gate: { official_hanja: "pass", caution: "none" } }} selected={false} onSelect={() => {}} onReact={() => {}} />);
    expect(screen.getByText("한글 이름")).toBeInTheDocument();
  });
});

describe("ScoreBar / RadarChart", () => {
  it("renders N/A without a filled bar", () => {
    const { container } = render(<ScoreBar label="사주" value={null} />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(container.querySelector(".bg-primary")).toBeNull();
  });
  it("radar marks series with N/A as dashed and explains it", () => {
    const { container } = render(<RadarChart series={[{ name: "심지아", categories: item.categories }]} />);
    expect(container.querySelector("polygon[stroke-dasharray]")).not.toBeNull();
    expect(screen.getByText(/점선 = N\/A/)).toBeInTheDocument();
  });
});

describe("AnalysisSections", () => {
  const analysis = {
    phonetics: { pronunciation: { written: "심지아", pronounced: "심지아", rules: [] }, ease_score: 93,
                 ease_rubric: { deductions: [{ feature: "vowel_hiatus", points: 3, count: 1, description: "모음 충돌" }] } },
    caution: { candidates: [], note: "판정 아님" },
    meaning: { status: "candidate", characters: [{ hanja: "智", definition_en: "wisdom", caution_keywords: [] }] },
    numerology: { applicability: { numerology: "applicable" }, stroke_system: "original",
                  characters: [{ hanja: "沈", strokes: 8 }, { hanja: "智", strokes: 12 }, { hanja: "雅", strokes: 12 }],
                  calc: { four_gyeok: { won: { value: 24, element: "火" }, hyeong: { value: 20, element: "水" }, i: { value: 20, element: "水" }, jeong: { value: 32, element: "木" } },
                          yinyang_pattern: ["음", "음", "음"] },
                  trad: { luck81: { won: { label: "길" }, hyeong: { label: "흉" }, i: { label: "흉" }, jeong: { label: "길", disputed: false } }, yinyang: { value: "편중" } },
                  eumryeong: { school: "modern-common", elements: ["金", "金", "土"], by_school: { "hunmin-haerye": { elements: ["金", "金", "水"] } } } },
    usability: { notes: [] },
    romanization: { surname_rr: "Sim", given_rr: "Ji-a", surname_customary_examples: ["Shim"], english_pitfalls: { items: [] }, note: "참고용" },
  };
  it("every ranking category shows its basis, nature and weights", () => {
    render(<AnalysisSections analysis={analysis} ranking={item} />);
    for (const label of ["발음·어감 근거", "이름 의미 근거", "전통 사주·오행 해석 근거", "희소성·개인 선호 근거"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText("전통 해석 · 출처 대조 전")).toBeInTheDocument();
    expect(screen.getByText(/운명을 결정하지 않습니다/)).toBeInTheDocument();
    expect(screen.getByText(/−3: 모음 충돌/)).toBeInTheDocument();
  });
});

describe("ConsentDialog", () => {
  it("lists exactly the fields to be sent and what is not sent", () => {
    const onConfirm = vi.fn();
    render(<ConsentDialog preview={{ provider_id: "claude_code", external: true, prompt_version: "v1",
      fields: [{ key: "sex", label: "성별 선호", value: "f" }], not_sent: ["출생일시", "가족 이름"] }}
      onConfirm={onConfirm} onCancel={() => {}} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("성별 선호")).toBeInTheDocument();
    expect(screen.getByText(/출생일시, 가족 이름/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "동의하고 보내기" }));
    expect(onConfirm).toHaveBeenCalled();
  });
});
