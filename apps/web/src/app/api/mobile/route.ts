import { NextRequest, NextResponse } from "next/server";
import QRCode from "qrcode";
import { canAccessLocalApi, MOBILE_COOKIE, pairingCode, validPairingCode } from "@/lib/mobile-access";
import { checkProxyRequest } from "@/lib/proxy-guard";

const headers = { "Cache-Control": "no-store" };

export async function POST(request: NextRequest) {
  const guard = checkProxyRequest("POST", request.headers, ["mobile"]);
  if (!guard.ok) return NextResponse.json({ connected: false }, { status: guard.status, headers });
  const payload = await request.json().catch(() => null);
  if (!validPairingCode(payload?.code)) return NextResponse.json({ connected: false }, { status: 403, headers });
  const response = NextResponse.json({ connected: true }, { headers });
  response.cookies.set(MOBILE_COOKIE, pairingCode(), { httpOnly: true, sameSite: "strict", path: "/" });
  return response;
}

export async function GET(request: NextRequest) {
  const origin = process.env.NAMECRAFT_LAN_ORIGIN;
  if (!origin || !pairingCode()) {
    return NextResponse.json({ enabled: false, reason: "lan_disabled" }, { headers });
  }
  if (!canAccessLocalApi(request)) {
    return NextResponse.json({ enabled: false, reason: "pairing_required" }, { status: 401, headers });
  }
  const url = `${origin}/connect#${pairingCode()}`;
  const qr = await QRCode.toDataURL(url, { width: 256, margin: 3 });
  return NextResponse.json({ enabled: true, qr, url }, { headers });
}
