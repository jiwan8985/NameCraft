import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { vi } from "vitest";
import { AnalyticsView } from "@/components/usage/analytics-view";
import { LineChart } from "@/components/usage/charts";
import { UsageCenter } from "@/components/usage/usage-center";

afterEach(() => vi.unstubAllGlobals());

const card = (pid: string, label: string, quota: unknown) => ({
  provider_id: pid, label, connection: { state: "disabled", message: "" },
  namecraft_usage: { scope: "NameCraft 안에서 실행한 요청만 — 계정 전체 사용량 아님", source_kind: "local_observed",
    today: { requests: 0 }, "7d": { requests: 1 }, "30d": { requests: 3, success_rate: null, avg_latency_ms: null, tokens_out: null } },
  quota,
});

describe("UsageCenter", () => {
  it("shows only Ollama usage even when historical external records exist", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify({ status: "ok", warnings: [], data:
      url.includes("alerts") ? [] : { rules: ["Provider 간 수치는 합산하지 않습니다."], providers: [
        card("ollama", "Ollama", { status: "not_applicable", label: "로컬 / 한도 없음 / 해당 없음", windows: [] }),
        card("claude_code", "Claude Code", { status: "unknown", label: "확인 불가 — 공식 /usage 화면 값을 직접 입력할 수 있습니다", windows: [] }),
        card("antigravity", "Google Antigravity", { status: "available", windows: [{ id: "q", window_type: "weekly", model_group: "all", used_pct: 77, remaining_pct: 23, reset_in_minutes: null, source_kind: "stale", observed_at: "2026-11-19T01:00" }] }),
      ] } }), { status: 200 })));
    render(<UsageCenter />);
    await waitFor(() => expect(screen.getByText("최근 30일 요청")).toBeInTheDocument());
    expect(screen.queryByText(/Claude|Antigravity|구독 한도/)).not.toBeInTheDocument();
    expect(screen.getAllByText("로컬 관측")).toHaveLength(1);
    expect(screen.getAllByText("확인 불가").length).toBeGreaterThan(0);
  });
});

describe("AnalyticsView", () => {
  it("keeps the view visual and refreshes charts after changing the period", async () => {
    const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify({ status: "ok", data:
      url.includes("heatmap")
        ? { weekday_hour: [[3]], weekdays: ["월"], model_distribution: [{ model_id: "qwen", requests: 3 }] }
        : { unit: "건", series: { ollama: [{ date: "2026-11-19", value: 3 }, { date: "2026-11-20", value: 5 }] } },
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    render(<AnalyticsView />);
    expect(await screen.findByRole("img", { name: "요청 수 추이 (건)" })).toBeInTheDocument();
    expect(await screen.findByText("qwen")).toBeInTheDocument();
    const day = screen.getByRole("button", { name: "2026-11-19 3 건" });
    fireEvent.click(day);
    expect(day).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("2026.11.19")).toBeInTheDocument();
    expect(screen.queryByText("표로 보기")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    const period = screen.getByRole("button", { name: "30일" });
    fireEvent.click(period);
    expect(period).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("heatmap?days=30"))).toBe(true));
  });
});

describe("LineChart", () => {
  it("breaks the line on null instead of drawing zero", () => {
    const { container } = render(<LineChart unit="ms" label="x" points={[{ date: "2026-11-17", value: 5 }, { date: "2026-11-18", value: null }, { date: "2026-11-19", value: 7 }]} />);
    expect(container.querySelectorAll("polyline")).toHaveLength(2);
    expect(container.querySelectorAll("circle")).toHaveLength(2);
  });
});

describe("service worker", () => {
  it("never caches API responses", () => {
    const sw = readFileSync(path.join(__dirname, "..", "..", "..", "public", "sw.js"), "utf-8");
    expect(sw).toContain('url.pathname.startsWith("/api/")) return;');
  });
});
