"use client";

import { useEffect, useState } from "react";
import { Bot, CheckCircle2, CircleAlert, Loader2, Power, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardDescription } from "@/components/ui/card";
import { Details, Field, Input, Notice, Select } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";
import { cn } from "@/lib/utils";

/* eslint-disable @typescript-eslint/no-explicit-any */
const NAME: Record<string, string> = { ollama: "Ollama", claude_code: "Claude Code", antigravity: "Google Antigravity" };
const SUB: Record<string, string> = { ollama: "내 PC 에서 도는 로컬 AI", claude_code: "보유한 구독 계정 사용", antigravity: "보유한 구독 계정 사용" };

function plainState(p: any): { text: string; tone: "ok" | "off" | "warn" } {
  if (p.state === "not_installed") return { text: p.provider_id === "ollama" ? "Ollama 앱이 실행 중이 아니에요" : "이 PC 에서 찾지 못했어요", tone: "warn" };
  if (!p.enabled) return { text: `찾았어요${p.version ? ` (${p.version})` : ""} · 꺼져 있음`, tone: "off" };
  if (p.provider_id === "ollama" && !p.selected_model) return { text: "켜져 있지만 쓸 수 있는 생성 모델이 없어요", tone: "warn" };
  return { text: `사용 중${p.selected_model ? ` · ${p.selected_model}` : ""}`, tone: "ok" };
}

export function AISettings() {
  const [list, setList] = useState<any[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, any>>({});
  const [cmd, setCmd] = useState<Record<string, string>>({});
  const load = () => apiFetch<any[]>("ai/providers").then((r) => r.ok ? setList(r.data) : setMsg(r.error.message));
  useEffect(() => { load(); }, []);

  async function save(id: string, patch: Record<string, unknown>) {
    const r = await postJson("ai/preferences", { provider_id: id, ...patch }, "PATCH");
    if (!r.ok) setMsg(r.error.message);
    await load();
  }
  async function test(id: string) {
    setTesting(id);
    const r = await postJson<any>(`ai/providers/${id}/test?live=true`, {});
    setTesting(null);
    setResults((x) => ({ ...x, [id]: r.ok ? r.data : { test_result: "error", test_message: r.error.message } }));
  }

  if (!list) return <p aria-busy="true" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> AI 확인 중…</p>;
  return (
    <div className="space-y-3">
      {msg && <Notice tone="danger" role="alert">{msg}</Notice>}
      {list.map((p) => {
        const st = plainState(p);
        const res = results[p.provider_id];
        const models = (p.models ?? []).filter((m: any) => m.can_generate);
        return (
          <Card key={p.provider_id} className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <span className={cn("grid h-10 w-10 place-items-center rounded-xl", st.tone === "ok" ? "bg-ok-soft text-ok" : st.tone === "warn" ? "bg-warn-soft text-warn" : "bg-muted text-muted-foreground")}>
                <Bot className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{NAME[p.provider_id]} <span className="ml-1 text-xs font-normal text-muted-foreground">{SUB[p.provider_id]}</span></p>
                <p className={cn("text-sm", st.tone === "ok" ? "text-ok" : st.tone === "warn" ? "text-warn" : "text-muted-foreground")}>{st.text}</p>
              </div>
              {p.state !== "not_installed" && (
                <Button size="sm" variant={p.enabled ? "outline" : "default"} onClick={() => save(p.provider_id, { enabled: !p.enabled })}>
                  <Power className="h-3.5 w-3.5" /> {p.enabled ? "끄기" : "사용하기"}
                </Button>
              )}
              {p.enabled && p.state !== "not_installed" && (
                <Button size="sm" variant="soft" disabled={testing === p.provider_id} onClick={() => test(p.provider_id)}>
                  {testing === p.provider_id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />} 연결 시험
                </Button>
              )}
            </div>
            {p.provider_id === "ollama" && p.enabled && models.length > 0 && (
              <Field label="사용할 모델" htmlFor="ollama-model">
                <Select id="ollama-model" value={p.selected_model ?? ""} onChange={(e) => save("ollama", { model_id: e.target.value })} className="max-w-sm">
                  {models.map((m: any) => <option key={m.name} value={m.name}>{m.name}</option>)}
                </Select>
              </Field>
            )}
            {res && (
              <p className={cn("flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm", res.test_result === "ok" ? "bg-ok-soft text-ok" : "bg-warn-soft text-warn")}>
                {res.test_result === "ok" ? <CheckCircle2 className="h-4 w-4" /> : <CircleAlert className="h-4 w-4" />}
                {res.test_result === "ok" ? `잘 돼요! ${res.test_message}` : res.test_message}
              </p>
            )}
            {p.provider_id !== "ollama" && p.enabled && <CardDescription>이름을 만들 때 보낼 내용을 먼저 보여 드리고, 동의해야 보내요. 성씨·출생정보·메모는 보내지 않아요.</CardDescription>}
            {p.provider_id !== "ollama" && (
              <Details summary="직접 설정 (보통은 필요 없음)">
                <div className="flex flex-wrap items-end gap-2">
                  <Field label="실행 명령" htmlFor={`cmd-${p.provider_id}`} hint={p.command ? `지금: ${p.command.join(" ")}` : "자동으로 찾지 못할 때만 입력"}>
                    <Input id={`cmd-${p.provider_id}`} value={cmd[p.provider_id] ?? ""} onChange={(e) => setCmd((c) => ({ ...c, [p.provider_id]: e.target.value }))} />
                  </Field>
                  <Button size="sm" variant="outline" disabled={!cmd[p.provider_id]} onClick={() => save(p.provider_id, { command: cmd[p.provider_id].split(/\s+/).filter(Boolean) })}>저장</Button>
                </div>
              </Details>
            )}
          </Card>
        );
      })}
    </div>
  );
}
