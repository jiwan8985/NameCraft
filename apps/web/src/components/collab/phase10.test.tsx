import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { RegistrationCheck } from "@/components/collab/registration-check";

afterEach(() => vi.unstubAllGlobals());

describe("RegistrationCheck", () => {
  it("never shows a final 'done' state and always shows disclaimer, links, checklist", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "ok", warnings: [], data: {
      name: { full: "심지아", full_hanja: "沈智雅" }, overall: "official_recheck_required", overall_label: "최종 공식 재확인 필요",
      checks: [{ id: "official_0", status: "recheck", message: "'智'(지) 공식 조회 필요" }],
      characters: [{ position: 0, hanja: "智", codepoint: "U+667A", hangul: "지", reading_match: true, official: "unknown", allowed_readings: [] }],
      data_basis: { official_data_loaded: false }, checklist: ["대법원 조회"], official_links: [{ label: "대법원", url: "https://efamily.scourt.go.kr/" }],
      disclaimer: "출생신고를 대신하거나 신고의 수리를 보장하지 않습니다.", never_final: true } }), { status: 200 })));
    render(<RegistrationCheck projectId="p1" refreshKey={0} />);
    await waitFor(() => expect(screen.getByText("최종 공식 재확인 필요")).toBeInTheDocument());
    expect(screen.getByText(/\[공식 재확인 필요\]/)).toBeInTheDocument();
    expect(screen.getByText(/수리를 보장하지 않습니다/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "대법원" })).toHaveAttribute("href", "https://efamily.scourt.go.kr/");
    expect(screen.getByText("공식 인명용 한자표 미적재", { exact: false })).toBeInTheDocument();
    expect(screen.queryByText(/완료/)).toBeNull();
  });
});
