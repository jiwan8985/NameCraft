"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, Check, Link2, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";
import { cn } from "@/lib/utils";

/* 이름을 '누구와' 지을지 고르는 곳. AI 연결은 설정 화면이 아니라 여기서 바로 한다.
   - 이 PC(Windows·WSL)에서 찾은 Claude Code·Antigravity 는 고르는 순간 켜진다.
   - 못 찾으면 '다른 컴퓨터와 연결(브리지)'로 주소·토큰만 넣으면 된다. */

export const AI_NAME: Record<string, string> = { claude_code: "Claude", antigravity: "Antigravity", ollama: "Ollama", none: "이름 사전" };
const AI_SUB: Record<string, string> = { claude_code: "Claude Code 구독으로", antigravity: "Google Antigravity 구독으로", ollama: "내 PC 로컬 AI" };

type Provider = { provider_id: string; enabled?: boolean; state: string; execution_mode: string; connection?: string; message?: string; version?: string | null };

export function useProviders() {
  const [list, setList] = useState<Provider[] | null>(null);
  const load = useCallback(() => apiFetch<Provider[]>("ai/providers").then((r) => { if (r.ok) setList(r.data); }), []);
  useEffect(() => { load(); }, [load]);
  return { list, reload: load };
}

const usable = (p: Provider) => p.enabled && ["supported_cli_task", "native_local"].includes(p.execution_mode);
const found = (p: Provider) => p.state !== "not_installed" && p.state !== "auth_required";

/** 실제로 고를 수 있는 선택지(쓸 수 있는 AI + 이름 사전). Ollama 는 켜서 쓸 수 있을 때만 보인다. */
export function pickable(list: Provider[] | null) {
  return (list ?? []).filter((p) => p.provider_id !== "ollama" ? true : usable(p));
}

export function defaultChoice(list: Provider[] | null): string {
  const ready = (list ?? []).find((p) => p.provider_id !== "ollama" && (usable(p) || found(p)));
  return ready?.provider_id ?? "none";
}

/** AI 를 고르면 보내는 내용 — 미리 보여 주고, 버튼을 누르는 것이 동의다. */
export function SendNote({ provider }: { provider: string }) {
  if (provider === "none") return <p className="text-xs text-muted-foreground">인터넷으로 아무것도 보내지 않아요. 요즘 아기 이름 사전에서 바로 골라 드려요.</p>;
  return (
    <p className="text-xs text-muted-foreground">
      {AI_NAME[provider]}에는 <b className="font-medium text-foreground">성별 · 글자 수 · 원하는 느낌 · 좋아한 이름</b>만 보내요.
      성씨 · 생일 · 가족 정보는 보내지 않아요. 구독 사용량이 조금 쓰여요.
    </p>
  );
}

export function AIPicker({ value, onChange, list, reload, compact = false }: {
  value: string; onChange: (v: string) => void; list: Provider[] | null; reload: () => void; compact?: boolean;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [bridgeFor, setBridgeFor] = useState<string | null>(null);
  const [bridge, setBridge] = useState({ url: "http://127.0.0.1:8787", token: "" });
  const [msg, setMsg] = useState<string | null>(null);

  async function choose(p: Provider) {
    setMsg(null);
    if (!found(p)) return setBridgeFor(p.provider_id);
    if (!p.enabled) {
      setBusy(p.provider_id);
      const r = await postJson("ai/preferences", { provider_id: p.provider_id, enabled: true }, "PATCH");
      setBusy(null);
      if (!r.ok) return setMsg(r.error.message);
      reload();
    }
    onChange(p.provider_id);
  }
  async function saveBridge(id: string) {
    setBusy(id);
    const r = await postJson("ai/preferences", { provider_id: id, connection: "bridge", enabled: true, bridge_url: bridge.url, bridge_token: bridge.token }, "PATCH");
    setBusy(null);
    if (!r.ok) return setMsg(r.error.message);
    setBridgeFor(null);
    reload();
    onChange(id);
  }

  if (!list) return <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 이 PC 의 AI 를 찾는 중…</p>;
  const ais = pickable(list);

  const options = [
    ...ais.map((p) => ({
      id: p.provider_id, title: AI_NAME[p.provider_id], icon: Sparkles,
      sub: !found(p) ? "이 PC 에서 찾지 못했어요 · 눌러서 연결" : `${AI_SUB[p.provider_id]} · 20~40초`,
      dim: !found(p), p,
    })),
    { id: "none", title: "이름 사전", icon: BookOpen, sub: "AI 없이 · 바로", dim: false, p: null as Provider | null },
  ];

  return (
    <div className="space-y-3">
      <div role="radiogroup" aria-label="함께 지을 AI" className={cn("grid gap-2", compact ? "grid-cols-3" : "sm:grid-cols-3")}>
        {options.map((o) => {
          const active = value === o.id;
          return (
            <button key={o.id} type="button" role="radio" aria-checked={active} disabled={busy !== null}
                    onClick={() => (o.p ? choose(o.p) : onChange("none"))}
                    className={cn("relative flex items-start gap-3 rounded-2xl border p-3 text-left transition",
                                  compact && "flex-col gap-1 p-2.5",
                                  active ? "border-primary bg-primary-soft ring-1 ring-primary" : "border-border bg-card hover:bg-muted",
                                  o.dim && !active && "opacity-70")}>
              <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", compact && "h-7 w-7 rounded-lg",
                                  active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>
                {busy === o.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <o.icon className="h-4 w-4" />}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold">{o.title}</span>
                <span className={cn("block text-xs text-muted-foreground", compact && "text-[11px] leading-tight")}>{o.sub}</span>
              </span>
              {active && <Check className="absolute right-2.5 top-2.5 h-4 w-4 text-primary" aria-hidden="true" />}
            </button>
          );
        })}
      </div>

      {bridgeFor && (
        <div className="space-y-3 rounded-2xl border border-border bg-muted/60 p-4">
          <p className="flex items-center gap-1.5 text-sm font-medium"><Link2 className="h-4 w-4" /> {AI_NAME[bridgeFor]} 를 다른 곳에서 연결하기</p>
          <ol className="list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
            <li>{AI_NAME[bridgeFor]} 가 설치된 컴퓨터(또는 WSL)에서 <code className="rounded bg-card px-1">namecraft bridge</code> 실행
              <span className="block">다른 PC 라면 <code className="rounded bg-card px-1">bridge/namecraft_bridge.py</code> 파일만 복사해 <code className="rounded bg-card px-1">python3 namecraft_bridge.py --lan</code></span></li>
            <li>화면에 나온 주소와 토큰을 아래에 넣기</li>
          </ol>
          <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <Input aria-label="브리지 주소" value={bridge.url} onChange={(e) => setBridge((b) => ({ ...b, url: e.target.value }))} />
            <Input aria-label="토큰" type="password" autoComplete="off" placeholder="토큰" value={bridge.token} onChange={(e) => setBridge((b) => ({ ...b, token: e.target.value }))} />
            <div className="flex gap-1">
              <Button size="sm" disabled={!bridge.url || !bridge.token || busy !== null} onClick={() => saveBridge(bridgeFor)}>연결</Button>
              <Button size="sm" variant="ghost" onClick={() => setBridgeFor(null)}>닫기</Button>
            </div>
          </div>
        </div>
      )}
      {msg && <p role="alert" className="text-xs text-danger">{msg}</p>}
    </div>
  );
}
