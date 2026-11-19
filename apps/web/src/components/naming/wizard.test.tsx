import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { NewProjectWizard } from "@/components/naming/new-project-wizard";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

describe("NewProjectWizard", () => {
  it("requires a Hangul surname before step 2 and states sex is not a restriction", () => {
    render(<NewProjectWizard />);
    const next = screen.getByRole("button", { name: "다음" });
    expect(next).toBeDisabled();
    expect(screen.getByText(/후보를 제한하지 않습니다/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("성씨 (한글)"), { target: { value: "Sim" } });
    expect(next).toBeDisabled();
    fireEvent.change(screen.getByLabelText("성씨 (한글)"), { target: { value: "심" } });
    fireEvent.click(next);
    expect(screen.getByText("원하는 느낌 (여러 개 선택)")).toBeInTheDocument();
    expect(screen.getByText("고급 옵션")).toBeInTheDocument();
  });
});
