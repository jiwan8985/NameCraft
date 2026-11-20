import { timingSafeEqual } from "node:crypto";
import type { NextRequest } from "next/server";

export const MOBILE_COOKIE = "namecraft_mobile";

export function pairingCode() {
  return process.env.NAMECRAFT_LAN_CODE || "";
}

export function validPairingCode(input: unknown): boolean {
  const expected = pairingCode();
  return typeof input === "string" && !!expected &&
    Buffer.byteLength(input) === Buffer.byteLength(expected) &&
    timingSafeEqual(Buffer.from(input), Buffer.from(expected));
}

export function canAccessLocalApi(request: NextRequest): boolean {
  return !pairingCode() || validPairingCode(request.cookies.get(MOBILE_COOKIE)?.value);
}
