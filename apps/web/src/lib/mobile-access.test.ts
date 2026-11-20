import { NextRequest } from "next/server";
import { afterEach, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/mobile/route";
import { canAccessLocalApi } from "@/lib/mobile-access";
import { CSRF_HEADER } from "@/lib/proxy-guard";

afterEach(() => vi.unstubAllEnvs());

it("requires the current QR code before exposing projects or the QR itself", async () => {
  vi.stubEnv("NAMECRAFT_LAN_CODE", "current-session");
  vi.stubEnv("NAMECRAFT_LAN_ORIGIN", "http://192.168.1.10:3000");
  const origin = "http://192.168.1.10:3000";
  const unauthenticated = new NextRequest(origin + "/api/mobile");
  const connect = (code: string) => POST(new NextRequest(origin + "/api/mobile", {
    method: "POST", headers: { [CSRF_HEADER]: "1", "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  }));

  expect(canAccessLocalApi(unauthenticated)).toBe(false);
  expect(await (await GET(unauthenticated)).json()).toEqual({ enabled: false, reason: "pairing_required" });
  expect((await connect("expired")).status).toBe(403);

  const connected = await connect("current-session");
  expect(connected.status).toBe(200);
  const cookie = connected.headers.get("set-cookie")!;
  expect(cookie).toMatch(/HttpOnly/i);
  const paired = new NextRequest(origin + "/api/mobile", { headers: { Cookie: cookie.split(";")[0] } });
  expect(canAccessLocalApi(paired)).toBe(true);
  expect(await (await GET(paired)).json()).toMatchObject({
    enabled: true,
    url: origin + "/connect#current-session",
    qr: expect.stringMatching(/^data:image\/png;base64,/),
  });

  vi.stubEnv("NAMECRAFT_LAN_CODE", "next-session");
  expect(canAccessLocalApi(paired)).toBe(false);
});

it("starts pairing before client bundles load and offers a retry after a network failure", async () => {
  const { GET: connectPage } = await import("@/app/connect/route");
  const html = await connectPage().text();
  const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
  expect(script).toBeTruthy();
  const status = { textContent: "" };
  const retry = { hidden: true, addEventListener: vi.fn() };
  const replace = vi.fn();
  const request = vi.fn()
    .mockRejectedValueOnce(new Error("network unavailable"))
    .mockResolvedValueOnce({ ok: true });
  const connect = new Function("document", "location", "fetch", script!);
  connect({ getElementById: (id: string) => id === "status" ? status : retry },
          { hash: "#pairing", replace }, request);

  await vi.waitFor(() => expect(retry.hidden).toBe(false));
  expect(status.textContent).toContain("다시 연결");
  expect(request.mock.calls[0][1]).toMatchObject({ method: "POST", body: '{"code":"pairing"}' });
  await retry.addEventListener.mock.calls[0][1]();
  expect(replace).toHaveBeenCalledWith("/dashboard");
});
