import { render, screen, waitFor } from "@testing-library/react";
import { ProviderList, type ProviderStatus } from "@/components/provider-list";
import { StatusBadge } from "@/components/status-badge";

const sample: ProviderStatus = {
  provider_id: "ollama", label: "Ollama", state: "unknown", execution_mode: "unavailable",
  message: "mock", models: [], last_checked_at: null, source_kind: "mock", is_mock: true,
  capabilities: { observe_quota: "n/a", generate_candidates: "supported" },
};

describe("ProviderList", () => {
  it("renders mock badge, warning and unknown last-check", async () => {
    const load = () => Promise.resolve({ ok: true as const, data: [sample], verification_status: "mock",
      warnings: [{ code: "mock_data", message: "Phase 1 mock 응답입니다." }] });
    render(<ProviderList load={load} />);
    await waitFor(() => expect(screen.getByText("Ollama")).toBeInTheDocument());
    expect(screen.getByText("MOCK")).toBeInTheDocument();
    expect(screen.getByText("Phase 1 mock 응답입니다.")).toBeInTheDocument();
    expect(screen.getByText("확인 불가")).toBeInTheDocument();
    expect(screen.getByText("해당 없음")).toBeInTheDocument(); // Ollama 한도: '무제한' 표기 금지
  });

  it("shows error UX with rule-based fallback notice", async () => {
    const load = () => Promise.resolve({ ok: false as const, httpStatus: 502,
      error: { code: "api_unreachable", message: "API 서버에 연결할 수 없습니다." } });
    render(<ProviderList load={load} />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText(/규칙 기반 작명/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("always shows a text label, not color only", () => {
    render(<StatusBadge status="demo" />);
    expect(screen.getByText("DEMO DATA")).toBeInTheDocument();
  });
});
