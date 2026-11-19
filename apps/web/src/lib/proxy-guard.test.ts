import { checkProxyRequest, CSRF_HEADER } from "@/lib/proxy-guard";

const h = (init: Record<string, string>) => new Headers(init);

describe("proxy guard", () => {
  it("allows same-origin GET", () => {
    expect(checkProxyRequest("GET", h({ "sec-fetch-site": "same-origin" }), ["ai", "providers"]).ok).toBe(true);
  });
  it("rejects cross-site requests", () => {
    expect(checkProxyRequest("GET", h({ "sec-fetch-site": "cross-site" }), ["health"])).toMatchObject({ ok: false, status: 403 });
  });
  it("requires CSRF header on mutating methods", () => {
    expect(checkProxyRequest("POST", h({}), ["ai", "providers", "ollama", "test"])).toMatchObject({ ok: false, code: "csrf_header_missing" });
    expect(checkProxyRequest("POST", h({ [CSRF_HEADER]: "1" }), ["ai", "providers", "ollama", "test"]).ok).toBe(true);
  });
  it("allows file-style paths like candidates.csv but not dot segments", () => {
    expect(checkProxyRequest("GET", h({}), ["projects", "p1", "candidates.csv"]).ok).toBe(true);
    expect(checkProxyRequest("GET", h({}), ["projects", ".", "x"]).ok).toBe(false);
    expect(checkProxyRequest("GET", h({}), ["..", "x"]).ok).toBe(false);
  });
  it("allows codepoint paths like hanja/U+6C88", () => {
    expect(checkProxyRequest("GET", h({}), ["hanja", "U+6C88"]).ok).toBe(true);
  });
  it("rejects path traversal and odd characters", () => {
    expect(checkProxyRequest("GET", h({}), ["..", "secret"]).ok).toBe(false);
    expect(checkProxyRequest("GET", h({}), ["ai?x=1"]).ok).toBe(false);
  });
});
