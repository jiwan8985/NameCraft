import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { FamilyView } from "@/components/collab/family-view";
import { ScenarioView } from "@/components/collab/scenario-view";
import { TournamentView } from "@/components/collab/tournament-view";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(), usePathname: () => "/x" }));

function stubApi(routes: Record<string, unknown>) {
  const calls: { url: string; body?: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const key = Object.keys(routes).find((k) => url.includes(k));
    return new Response(JSON.stringify({ status: "ok", data: key ? routes[key] : null, warnings: [] }), { status: 200 });
  }));
  return calls;
}

const cand = (id: string, n: string) => ({ id, given_hangul: n, given_hanja: null, full_hangul: "심" + n, overall: 80,
  gate: { official_hanja: "pass", caution: "none" }, categories: {}, incomplete: [], confidence: {}, ai_reason: null });

afterEach(() => vi.unstubAllGlobals());

describe("ScenarioView", () => {
  it("saves a due date without assuming a birth time", async () => {
    const calls = stubApi({
      "/scenario": null,
      "/birth-profiles": [],
      "projects/p1": { id: "p1", preferences: {} },
    });
    render(<ScenarioView projectId="p1" />);
    expect(screen.getByLabelText("시각")).toHaveValue("unknown");
    fireEvent.change(screen.getByLabelText("날짜"), { target: { value: "2027-01-15" } });
    fireEvent.click(screen.getByRole("button", { name: "저장하고 계산" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("저장했습니다."));
    const body = calls.find((call) => call.url.endsWith("/birth-profiles") && call.body)?.body;
    expect(body).toMatchObject({ kind: "expected", date: "2027-01-15" });
    expect(body).not.toHaveProperty("time");
    expect(body).not.toHaveProperty("time_range");
  });

  it("shows scenarios without averaging and the single-school disclaimer", async () => {
    stubApi({
      "/scenario": { profile: { kind: "expected" }, scenario: {
        scenario_count: 2, distinct_charts: 2, varying_pillars: ["hour"], notes: ["시나리오별 값을 평균하지 않습니다."],
        element_ranges: { 木: { min: 1, max: 2 } }, names: [],
        scenarios: [{ id: "a", date: "2027-01-15", offset_days: 0, from_local: "2027-01-15T09:00:00", to_local: "2027-01-15T11:00:00", text: "丙午 辛丑 甲午 己巳", changed: [] }],
        interpretation: { disclaimer: "한 학파의 단순 보완설" } } },
      "/birth-profiles": [], "projects/p1": { id: "p1", preferences: {} },
    });
    render(<ScenarioView projectId="p1" />);
    await waitFor(() => expect(screen.getByText(/시나리오 2개/)).toBeInTheDocument());
    expect(screen.getByText("시나리오별 값을 평균하지 않습니다.")).toBeInTheDocument();
    expect(screen.getByText(/단순 보완설/)).toBeInTheDocument();
    expect(screen.getByText("1~2")).toBeInTheDocument();
  });
});

describe("TournamentView", () => {
  it("offers A / B / hold per match", async () => {
    const calls = stubApi({
      "/candidates": { items: [cand("c1", "지아"), cand("c2", "하은")] },
      "/tournaments/t1/vote": { id: "t1", status: "done", rounds: [], result: { winner_name: "심지아", tied: false, finalist_names: [] } },
      "/tournaments": [{ id: "t1", status: "active", created_at: "2026-11-19T00:00", result: {},
        rounds: [[{ a: "c1", b: "c2", choice: null, a_name: "지아", b_name: "하은" }]] }],
    });
    render(<TournamentView projectId="p1" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "지아" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "보류" })).toBeInTheDocument();
    expect(screen.getByText(/둘 다 다음 라운드로/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "보류" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("/vote") && (c.body as { choice: string }).choice === "hold")).toBe(true));
  });
});

describe("FamilyView", () => {
  it("explains member votes never exclude candidates and lists disagreements", async () => {
    stubApi({
      "/candidates": { items: [cand("c1", "지아")] },
      "/family": { members: [{ id: "m1", alias: "엄마" }, { id: "m2", alias: "아빠" }],
        candidates: [{ candidate_id: "c1", votes: { m1: { reaction: "like" }, m2: { reaction: "dislike" } } }],
        common: [], disagreements: [{ candidate_id: "c1", given_hangul: "지아", like_count: 1, voted: 2 }] },
    });
    render(<FamilyView projectId="p1" />);
    await waitFor(() => expect(screen.getByText(/제외시키지 않습니다/)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "엄마 심지아 좋아요" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/지아 — 좋아요 1\/2/)).toBeInTheDocument();
  });
});
