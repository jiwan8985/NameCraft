import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";
import { checkProxyRequest } from "@/lib/proxy-guard";

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
      body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.text(),
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json(errorBody("api_unreachable", "API 서버에 연결할 수 없습니다."), { status: 502 });
  }
}

export { handle as GET, handle as POST, handle as PATCH, handle as DELETE };
