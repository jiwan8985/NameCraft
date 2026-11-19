"use client";

import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Input, Notice } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";
import type { ProviderStatus } from "@/components/provider-list";

/** AI 사용 설정 — 사용 여부·실행 명령·모델. 구독형은 기본 꺼짐, 유료 API 키 입력란 없음(§33.1). */
export function AISettings() {
  const [list, setList] = useState<ProviderStatus[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [cmd, setCmd] = useState<Record<string, string>>({});
  const [model, setModel] = useState<Record<string, string>>({});
  const load = () => apiFetch<ProviderStatus[]>("ai/providers").then((r) => r.ok ? setList(r.data) : setMsg(r.error.message));
  useEffect(() => { load(); }, []);

  async function save(id: string, patch: Record<string, unknown>) {
    const r = await postJson("ai/preferences", { provider_id: id, ...patch }, "PATCH");
    setMsg(r.ok ? "저장했습니다." : r.error.message);
    load();
  }
  if (!list) return <p aria-busy="true" className="text-sm text-muted-foreground">불러오는 중…</p>;
  return (
    <div className="space-y-4">
      {msg && <Notice role="status">{msg}</Notice>}
      {list.map((p) => {
        const enabled = !!p.enabled;
        return (
          <Card key={p.provider_id} className="space-y-3">
            <div className="flex items-center justify-between"><CardTitle>{p.label}</CardTitle><StatusBadge status={p.source_kind} /></div>
            <CardDescription>{p.message}</CardDescription>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant={enabled ? "outline" : "default"} onClick={() => save(p.provider_id, { enabled: !enabled })}>
                {enabled ? "사용 안 함으로" : "사용하기"}
              </Button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {p.provider_id !== "ollama" && (
                <Field label="실행 명령 (공백 구분)" htmlFor={`cmd-${p.provider_id}`} hint="예: wsl.exe -e /home/사용자/.local/bin/claude">
                  <Input id={`cmd-${p.provider_id}`} value={cmd[p.provider_id] ?? ""} onChange={(e) => setCmd((c) => ({ ...c, [p.provider_id]: e.target.value }))} />
                </Field>
              )}
              <Field label="모델" htmlFor={`model-${p.provider_id}`}>
                <Input id={`model-${p.provider_id}`} value={model[p.provider_id] ?? ""} onChange={(e) => setModel((m) => ({ ...m, [p.provider_id]: e.target.value }))} />
              </Field>
            </div>
            <Button size="sm" variant="outline" onClick={() => save(p.provider_id, {
              ...(cmd[p.provider_id] ? { command: cmd[p.provider_id].split(/\s+/).filter(Boolean) } : {}),
              ...(model[p.provider_id] ? { model_id: model[p.provider_id] } : {}),
            })}>명령·모델 저장</Button>
          </Card>
        );
      })}
    </div>
  );
}
