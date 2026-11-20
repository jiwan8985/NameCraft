import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { apiFetch, postJson } from "@/lib/api";
import { NewProjectWizard } from "@/components/naming/new-project-wizard";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async () => ({ ok: true, data: [] })),
  postJson: vi.fn(async () => ({ ok: true, warnings: [], data: { id: "p1" } })),
}));

describe("NewProjectWizard", () => {
  it("starts from one form and accepts a due date without a birth time", async () => {
    render(<NewProjectWizard />);
    const generate = screen.getByRole("button", { name: "이름 받기" });
    expect(generate).toBeDisabled();
    fireEvent.change(screen.getByLabelText("성"), { target: { value: "Sim" } });
    expect(generate).toBeDisabled();
    fireEvent.change(screen.getByLabelText("성"), { target: { value: "심" } });
    expect(screen.getByRole("radio", { name: "아직 몰라요" })).toBeChecked();
    fireEvent.click(screen.getByText("사주 반영하기 · 선택"));
    fireEvent.change(screen.getByLabelText("출산 예정일"), { target: { value: "2027-01-15" } });
    fireEvent.click(screen.getByText("추천 방식 · 이름 사전"));
    expect(screen.queryByRole("radio", { name: /Claude|Antigravity/ })).not.toBeInTheDocument();
    await waitFor(() => expect(generate).toBeEnabled());
    fireEvent.click(generate);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/projects/p1/recommendations?sort=saju"));
    expect(postJson).toHaveBeenCalledWith("projects", expect.objectContaining({
      sex: "n", birth: { kind: "expected", calendar: "solar", date: "2027-01-15", time: null, is_leap_month: false },
    }));
  });

  it("offers a direct AI request when a local model is available", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({
      ok: true, data: { models: [{ can_generate: true }] }, warnings: [], verification_status: null,
    });
    render(<NewProjectWizard />);
    fireEvent.change(screen.getByLabelText("성"), { target: { value: "김" } });
    fireEvent.click(screen.getByRole("radio", { name: "남자 아기" }));
    const generate = await screen.findByRole("button", { name: "AI로 이름 받기" });
    expect(screen.getByText("추천 방식 · Ollama")).toBeInTheDocument();
    fireEvent.click(generate);
    await waitFor(() => expect(postJson).toHaveBeenCalledWith("projects/p1/candidates/generate", {
      provider: "ollama", local_only: true, count: 5,
    }));
  });
});
