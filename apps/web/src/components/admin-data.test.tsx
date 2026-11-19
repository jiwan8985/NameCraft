import { render, screen } from "@testing-library/react";
import { AdminDataView, type AdminData } from "@/components/admin-data";

const data: AdminData = {
  summary: { hanja_characters: 8525, hanja_readings: 8917, official_rules: 0, original_stroke_counts: 0 },
  sources: [{ id: "SRC-SCOURT-HANJA", name: "대법원 인명용 한자표", authority: "official_legal", license: null, status: "license_review", notes: null }],
  releases: [{ id: "unihan-18.0.0-4c93ea9c", description: "Unihan", checksums: { "Unihan.zip": "4c93" }, is_sample: true, created_at: null }],
};

describe("AdminDataView", () => {
  it("warns when official data missing and shows sample releases as DEMO", () => {
    render(<AdminDataView data={data} />);
    expect(screen.getByRole("status")).toHaveTextContent("공식 인명용 한자표가 적재되지 않았습니다");
    expect(screen.getByText("8,525")).toBeInTheDocument();
    expect(screen.getByText("이용조건 검토 중")).toBeInTheDocument();
    expect(screen.getByText("미확인")).toBeInTheDocument();
    expect(screen.getByText("DEMO DATA")).toBeInTheDocument();
  });
});
