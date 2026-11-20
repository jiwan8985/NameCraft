"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Field, Input, Notice, Select } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

type Session = {
  id: string;
  observed_at: string;
  model_id: string | null;
  task: string;
  status: string;
  duration_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
};

const statusNames: Record<string, string> = {
  success: "완료", error: "오류", timeout: "시간 초과", rate_limited: "호출 제한",
  invalid_output: "응답 형식 오류", unavailable: "사용 불가",
};
const taskNames: Record<string, string> = { generate_candidates: "이름 추천", explain_name: "이름 설명" };
const dateFormat = new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium", timeStyle: "short" });
const valueFormat = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 });

export function SessionsView() {
  const [rows, setRows] = useState<Session[] | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({ limit: "200", provider: "ollama" });
    if (status) params.set("status", status);
    if (search.trim()) params.set("q", search.trim().slice(0, 50));
    setRows(null);
    setError("");
    apiFetch<Session[]>(`ai/sessions?${params}`).then((result) => {
      if (!active) return;
      if (result.ok) setRows(result.data);
      else setError(result.error.message);
    });
    return () => { active = false; };
  }, [status, search]);

  return (
    <div className="space-y-4">
      <Card className="grid gap-3 sm:grid-cols-2">
        <Field label="결과" htmlFor="fs">
          <Select id="fs" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">모든 결과</option>
            {Object.entries(statusNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
        </Field>
        <Field label="모델·작업 검색" htmlFor="fq">
          <Input id="fq" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="예: qwen" maxLength={50} />
        </Field>
      </Card>
      {error ? <Notice tone="danger" role="alert">{error}</Notice>
        : !rows ? <p role="status" className="text-sm text-muted-foreground">요청 기록을 불러오고 있어요.</p>
        : !rows.length ? <Card className="text-sm text-muted-foreground">{status || search ? "이 조건에 맞는 기록이 없어요." : "아직 기록된 Ollama 요청이 없어요."}</Card>
        : (
          <ul className="space-y-2">
            {rows.map((row) => (
              <li key={row.id}>
                <Card className="flex flex-wrap justify-between gap-x-4 gap-y-2 p-4">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold">{taskNames[row.task] ?? row.task}</p>
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", row.status === "success" ? "bg-primary-soft text-primary" : "bg-muted text-muted-foreground")}>
                        {statusNames[row.status] ?? row.status}
                      </span>
                    </div>
                    <p className="break-all text-xs text-muted-foreground">{row.model_id ?? "모델 정보 없음"}</p>
                  </div>
                  <div className="space-y-1 text-xs text-muted-foreground sm:text-right">
                    <time dateTime={row.observed_at}>{dateFormat.format(new Date(row.observed_at))}</time>
                    <p className="tabular-nums">
                      {row.duration_ms == null ? "응답 시간 미보고" : `${valueFormat.format(row.duration_ms / 1000)}초`}
                      {(row.tokens_in != null || row.tokens_out != null) && ` · 토큰 ${row.tokens_in ?? "—"} / ${row.tokens_out ?? "—"}`}
                    </p>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
    </div>
  );
}
