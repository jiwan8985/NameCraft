import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { NewProjectWizard } from "@/components/naming/new-project-wizard";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async () => ({ ok: true, warnings: [], data: [
    { provider_id: "claude_code", enabled: false, state: "disabled", execution_mode: "manual_handoff" },
    { provider_id: "antigravity", enabled: false, state: "not_installed", execution_mode: "manual_handoff" },
    { provider_id: "ollama", enabled: false, state: "disabled", execution_mode: "unavailable" },
  ] })),
  postJson: vi.fn(async () => ({ ok: true, warnings: [], data: {} })),
}));

describe("NewProjectWizard", () => {
  it("needs a Hangul surname and baby sex, then lets you pick who names with", async () => {
    render(<NewProjectWizard />);
    const next = screen.getByRole("button", { name: "다음" });
    expect(next).toBeDisabled();
    fireEvent.change(screen.getByLabelText("성"), { target: { value: "Sim" } });
    fireEvent.click(screen.getByRole("button", { name: "여자 아기" }));
    expect(next).toBeDisabled();
    fireEvent.change(screen.getByLabelText("성"), { target: { value: "심" } });
    expect(next).toBeEnabled();
    fireEvent.click(next);
    expect(screen.getByText("누구와 함께 지을까요?")).toBeInTheDocument();
    // 이 PC 에서 찾은 Claude 가 기본 선택, Ollama 는 쓸 수 없으니 보이지 않음
    await waitFor(() => expect(screen.getByRole("radio", { name: /Claude/ })).toHaveAttribute("aria-checked", "true"));
    expect(screen.queryByRole("radio", { name: /Ollama/ })).toBeNull();
    expect(screen.getByRole("radio", { name: /Antigravity.*찾지 못했어요/ })).toBeInTheDocument();
    expect(screen.getByText(/성씨 · 생일 · 가족 정보는 보내지 않아요/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Claude에게 이름 받기/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /이름 사전/ }));
    expect(screen.getByRole("button", { name: /^이름 받기/ })).toBeInTheDocument();
  });
});
