/**
 * 서버 측 프록시 보호 규칙 (기획서 §31.2 — CSRF·권한 경계).
 * 프록시가 로컬 토큰을 자동으로 붙이므로, 교차 출처 요청은 반드시 거부한다.
 */
export const CSRF_HEADER = "x-namecraft-request";
const SAFE_METHODS = new Set(["GET", "HEAD"]);
const ALLOWED_PATH = /^[A-Za-z0-9\-_/+]+$/; // 예: hanja/U+6C88

export type GuardResult = { ok: true } | { ok: false; status: number; code: string };

export function checkProxyRequest(method: string, headers: Headers, path: string[]): GuardResult {
  const site = headers.get("sec-fetch-site");
  if (site && site !== "same-origin" && site !== "none") {
    return { ok: false, status: 403, code: "cross_site_request" };
  }
  if (!SAFE_METHODS.has(method.toUpperCase()) && headers.get(CSRF_HEADER) !== "1") {
    return { ok: false, status: 403, code: "csrf_header_missing" };
  }
  const joined = path.join("/");
  if (!ALLOWED_PATH.test(joined) || path.some((seg) => seg === ".." || seg === "")) {
    return { ok: false, status: 400, code: "invalid_path" };
  }
  return { ok: true };
}
