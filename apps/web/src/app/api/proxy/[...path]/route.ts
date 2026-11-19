import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";
import { checkProxyRequest, isSlowAICall } from "@/lib/proxy-guard";

/** 브라우저 → Next 서버 → FastAPI. 로컬 토큰은 서버에서만 읽고 브라우저로 내보내지 않는다. */
const API_URL = process.env.NAMECRAFT_API_URL ?? "http://127.0.0.1:8000";
const TOKEN_FILE = process.env.NAMECRAFT_TOKEN_FILE ?? path.resolve(process.cwd(), "..", "..", "var", "local_token");

async function readToken(): Promise<string | null> {
  try {
    return (await readFile(/*turbopackIgnore: true*/ TOKEN_FILE, "utf-8")).trim() || null;
  } catch {
    return null;
  }
}

function errorBody(code: string, message: string) {
  return { status: "error", error: { code, message, details: {} } };
}

async function handle(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path: segments } = await ctx.params;
  const guard = checkProxyRequest(req.method, req.headers, segments);
  if (!guard.ok) return NextResponse.json(errorBody(guard.code, "요청이 거부되었습니다."), { status: guard.status });

  const token = await readToken();
  if (!token) {
    return NextResponse.json(
      errorBody("api_token_missing", "API 서버가 아직 실행되지 않았거나 로컬 토큰이 없습니다. API를 먼저 실행하세요."),
      { status: 503 },
    );
  }

  const target = `${API_URL}/api/v1/${segments.join("/")}${req.nextUrl.search}`;
  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": req.headers.get("content-type") ?? "application/json" },
      // 바이너리 업로드(multipart)를 깨뜨리지 않도록 원본 바이트 그대로 전달
      body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.arrayBuffer(),
      cache: "no-store",
      // AI 생성·연결 시험은 구독형 CLI 가 20~40초(느리면 몇 분) 걸린다 — 15초로 끊으면 '연결 불가'처럼 보였음
      signal: AbortSignal.timeout(isSlowAICall(segments) ? 600_000 : 30_000),
    });
    const passthrough = ["content-type", "content-disposition", "x-content-type-options", "content-security-policy"];
    const headers = new Headers();
    for (const h of passthrough) {
      const v = upstream.headers.get(h);
      if (v) headers.set(h, v);
    }
    if (!headers.has("content-type")) headers.set("content-type", "application/json");
    return new NextResponse(upstream.body, { status: upstream.status, headers });
  } catch {
    return NextResponse.json(errorBody("api_unreachable", "API 서버에 연결할 수 없습니다."), { status: 502 });
  }
}

export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };

