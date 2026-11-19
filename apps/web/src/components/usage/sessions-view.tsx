"use client";

import { useCallback, useEffect, useState } from "react";
import { DemoBar, useDemoToggle } from "@/components/usage/usage-center";
import { StatusBadge } from "@/components/status-badge";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
export function SessionsView() {
  const { demo, setDemo, q } = useDemoToggle();
  const [rows, setRows] = useState<any[]>([]);
  const [f, setF] = useState({ provider: "", status: "", q: "" });
  const load = useCallback(() => {
    const p = new URLSearchParams({ include_demo: String(demo), limit: "200" });
    if (f.provider) p.set("provider", f.provider);
    if (f.status) p.set("status", f.status);
    if (f.q) p.set("q", f.q);
    apiFetch<any[]>(`ai/sessions?${p}`).then((r) => r.ok && setRows(r.data));
  }, [demo, f]);
  useEffect(() => { load(); }, [load, q]);
  return (
    <div className="space-y-4">
      <DemoBar demo={demo} setDemo={setDemo} onChange={load} />
      <Card className="grid gap-2 sm:grid-cols-3">
        <Field label="Provider" htmlFor="fp"><Select id="fp" value={f.provider} onChange={(e) => setF((x) => ({ ...x, provider: e.target.value }))}>
          <option value="">전체</option><option value="ollama">Ollama</option><option value="claude_code">Claude Code</option><option value="antigravity">Antigravity</option></Select></Field>
        <Field label="결과" htmlFor="fs"><Select id="fs" value={f.status} onChange={(e) => setF((x) => ({ ...x, status: e.target.value }))}>
          <option value="">전체</option>{["success", "error", "timeout", "rate_limited", "invalid_output", "unavailable"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
        <Field label="검색(작업·모델)" htmlFor="fq"><Input id="fq" value={f.q} onChange={(e) => setF((x) => ({ ...x, q: e.target.value }))} /></Field>
      </Card>
      <Card className="overflow-x-auto">
        <p className="mb-2 text-xs text-muted-foreground">NameCraft 가 실행한 AI 요청만 기록합니다. 프롬프트 원문·출생정보·인증 정보는 저장하지 않습니다.</p>
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-left text-xs text-muted-foreground"><tr><th>시각</th><th>Provider</th><th>모델</th><th>작업</th><th>결과</th><th>시간</th><th>토큰(입/출)</th><th>출처</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.id} className="border-t border-border"><td className="py-1 text-xs">{r.observed_at.slice(5, 16)}</td><td>{r.provider_id}</td><td className="text-xs">{r.model_id ?? "—"}</td>
              <td className="text-xs">{r.task}</td><td className="text-xs">{r.status}</td><td className="tabular-nums text-xs">{r.duration_ms ?? "—"}</td>
              <td className="tabular-nums text-xs">{r.tokens_in ?? "—"}/{r.tokens_out ?? "—"}</td><td><StatusBadge status={r.is_demo ? "demo" : r.source_type} /></td></tr>))}</tbody>
        </table>
        {rows.length === 0 && <p className="text-sm text-muted-foreground">기록이 없습니다.</p>}
      </Card>
    </div>
  );
}
