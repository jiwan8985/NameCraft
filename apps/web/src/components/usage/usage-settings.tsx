"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Input, Notice } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
export function UsageSettings() {
  const [rules, setRules] = useState<any[]>([]);
  const [s, setS] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => {
    apiFetch<any[]>("ai/alert-rules").then((r) => r.ok && setRules(r.data.filter((rule) => rule.provider_id === "ollama")));
    apiFetch<any>("ai/usage/settings").then((r) => r.ok && setS(r.data));
  };
  useEffect(load, []);
  async function saveRule(r: any, thresholds: string, enabled: boolean) {
    const t = thresholds.split(/[\s,]+/).filter(Boolean).map(Number);
    const x = await postJson("ai/alert-rules", { provider_id: r.provider_id, thresholds: t, enabled }, "PATCH");
    setMsg(x.ok ? "저장했습니다." : x.error.message); load();
  }
  async function saveRetention(days: number) {
    const x = await postJson("ai/usage/settings", { retention_days: days }, "PATCH");
    setMsg(x.ok ? "저장했습니다." : x.error.message); load();
  }
  async function purge() {
    const x = await postJson<any>("ai/usage/purge", {});
    setMsg(x.ok ? `보존 기간이 지난 기록 ${x.data.deleted_invocations}건을 지웠습니다.` : x.error.message);
  }
  return (
    <div className="space-y-4">
      {msg && <Notice role="status">{msg}</Notice>}
      <Card className="space-y-2">
        <CardTitle>수집 범위</CardTitle>
        <CardDescription>NameCraft 안에서 실행한 AI 요청의 메타데이터(시각·Provider·모델·결과·시간·보고된 토큰 수)만 기록합니다.</CardDescription>
        <p className="text-sm">다른 도구의 로컬 로그·인증 폴더 읽기: <b>지원 안 함</b> — {s?.local_log_collection.message}</p>
      </Card>
      <Card className="space-y-3">
        <CardTitle>알림 임계치</CardTitle>
        <CardDescription>로컬 Ollama 요청이 늘어날 때 사용량을 확인할 수 있어요.</CardDescription>
        {rules.map((r) => <RuleRow key={r.provider_id} r={r} onSave={saveRule} />)}
      </Card>
      {s && (
        <Card className="flex flex-wrap items-end gap-2">
          <RetentionField days={s.retention_days} onSave={saveRetention} />
          <Button variant="outline" onClick={purge}>지금 정리</Button>
        </Card>
      )}
    </div>
  );
}

function RuleRow({ r, onSave }: { r: any; onSave: (r: any, t: string, e: boolean) => void }) {
  const [t, setT] = useState(r.thresholds.join(", "));
  const [e, setE] = useState(r.enabled);
  return (
    <div className="flex flex-wrap items-end gap-2">
      <Field label={`${r.provider_id} 임계치(%)`} htmlFor={`t-${r.provider_id}`}><Input id={`t-${r.provider_id}`} value={t} onChange={(x) => setT(x.target.value)} /></Field>
      <label className="inline-flex items-center gap-1 text-sm"><input type="checkbox" checked={e} onChange={(x) => setE(x.target.checked)} /> 사용</label>
      <Button size="sm" variant="outline" onClick={() => onSave(r, t, e)}>저장</Button>
    </div>
  );
}

function RetentionField({ days, onSave }: { days: number; onSave: (d: number) => void }) {
  const [d, setD] = useState(String(days));
  return (
    <>
      <Field label="사용량 기록 보존 기간(일)" htmlFor="ret"><Input id="ret" inputMode="numeric" value={d} onChange={(x) => setD(x.target.value)} /></Field>
      <Button size="sm" onClick={() => onSave(Number(d))}>저장</Button>
    </>
  );
}
