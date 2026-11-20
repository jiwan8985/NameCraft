import { NextRequest } from "next/server";
import { pairingCode } from "@/lib/mobile-access";

export function GET(request: NextRequest) {
  const host = request.headers.get("host");
  if (pairingCode() && (host === "127.0.0.1:3000" || host === "localhost:3000")) {
    return new Response(null, {
      status: 302,
      headers: { Location: "http://127.0.0.1:3001/mobile", "Cache-Control": "no-store" },
    });
  }
  return new Response(`<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>휴대폰에서 열기</title>
<main><h1>휴대폰에서 열기</h1>
<p>PC에서 NameCraft 명령 메뉴의 1번으로 앱을 열고, PC 홈에서 휴대폰 접속 QR을 확인하세요.</p>
<a href="/dashboard">작명 홈으로</a></main></html>`, {
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
  });
}
