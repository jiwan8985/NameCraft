import { CSRF_HEADER } from "@/lib/proxy-guard";

export type ApiError = { code: string; message: string; details?: Record<string, unknown> };
export type ApiResult<T> =
  | { ok: true; data: T; warnings: { code: string; message: string }[]; verification_status: string | null }
  | { ok: false; error: ApiError; httpStatus: number };

/** 브라우저에서 같은 출처 프록시(/api/proxy)를 호출한다. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`/api/proxy/${path.replace(/^\//, "")}`, {
      ...init,
      headers: { ...(init?.headers ?? {}), [CSRF_HEADER]: "1" },
      cache: "no-store",
    });
    const body = await res.json().catch(() => null);
    if (!res.ok || !body || body.status === "error") {
      return {
        ok: false,
        httpStatus: res.status,
        error: body?.error ?? { code: "invalid_response", message: "응답을 해석할 수 없습니다." },
      };
    }
    return { ok: true, data: body.data as T, warnings: body.warnings ?? [], verification_status: body.verification_status ?? null };
  } catch {
    return { ok: false, httpStatus: 0, error: { code: "network_error", message: "네트워크 오류가 발생했습니다." } };
  }
}

export function postJson<T>(path: string, body: unknown, method: "POST" | "PATCH" = "POST") {
  return apiFetch<T>(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
