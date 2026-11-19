import { existsSync } from "node:fs";
import path from "node:path";
import { ROUTES } from "@/lib/routes";

// 기획서 §15 화면 IA 전체
const PLAN_ROUTES = [
  "/dashboard", "/projects/new", "/projects/[id]/recommendations", "/names/analyze", "/names/[id]",
  "/compare", "/scenario", "/tournament", "/family", "/imports", "/finalize", "/reports", "/settings",
  "/ai/providers", "/ai/usage", "/ai/sessions", "/ai/analytics", "/ai/settings", "/admin/data",
];

describe("route registry", () => {
  it("covers every IA route in the master plan", () => {
    expect(ROUTES.map((r) => r.path).sort()).toEqual([...PLAN_ROUTES].sort());
  });
  it("has a page file for every route", () => {
    for (const r of ROUTES) {
      expect(existsSync(path.join(__dirname, "..", "app", r.path, "page.tsx")), r.path).toBe(true);
    }
  });
});
