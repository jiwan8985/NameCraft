import { render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { vi } from "vitest";
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
  it("distinguishes local-observed, unknown, not-applicable and manual/stale sources", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify({ status: "ok", warnings: [], data:
      url.includes("alerts") ? [] : { rules: ["Provider 간 수치는 합산하지 않습니다."], providers: [
        card("ollama", "Ollama", { status: "not_applicable", label: "로컬 / 한도 없음 / 해당 없음", windows: [] }),
        card("claude_code", "Claude Code", { status: "unknown", label: "확인 불가 — 공식 /usage 화면 값을 직접 입력할 수 있습니다", windows: [] }),
        card("antigravity", "Google Antigravity", { status: "available", windows: [{ id: "q", window_type: "weekly", model_group: "all", used_pct: 77, remaining_pct: 23, reset_in_minutes: null, source_kind: "stale", observed_at: "2026-11-19T01:00" }] }),
      ] } }), { status: 200 })));
    render(<UsageCenter />);
    await waitFor(() => expect(screen.getByText("Ollama")).toBeInTheDocument());
    expect(screen.getByText(/로컬 \/ 한도 없음 \/ 해당 없음/)).toBeInTheDocument();
    expect(screen.getByText(/확인 불가 — 공식 \/usage/)).toBeInTheDocument();
    expect(screen.getAllByText("로컬 관측").length).toBe(3);
    expect(screen.getByText("오래됨")).toBeInTheDocument();
    expect(screen.getAllByText(/계정 전체 사용량 아님/).length).toBe(3);
    expect(screen.queryByText(/합계|총 AI/)).toBeNull();
    expect(screen.getAllByText("확인 불가").length).toBeGreaterThan(0); // 보고값 없음
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
