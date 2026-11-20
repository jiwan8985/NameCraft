"use client";

import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { apiFetch, type ApiResult } from "@/lib/api";

export type ProviderStatus = {
  provider_id: string;
  label: string;
  state: string;
  execution_mode: string;
  message: string;
  models: string[];
  selected_model?: string | null;
  last_checked_at: string | null;
  source_kind: string;
  is_mock: boolean;
  enabled?: boolean;
  capabilities: Record<string, string>;
};

const STATE_LABEL: Record<string, string> = {
  connected: "연결됨",
  not_installed: "미설치",
  auth_required: "로그인 필요",
  disabled: "비활성(사용자 설정)",
  error: "오류",
  unknown: "확인 전",
};

const CAP_LABEL: Record<string, string> = {
  generate_candidates: "후보 생성",
  explain_name: "이름 설명",
  summarize_comparison: "비교 요약",
  healthcheck: "상태 확인",
  list_models: "모델 목록",
  observe_usage: "사용량 관측",
  observe_quota: "한도 관측",
};

const LEVEL_LABEL: Record<string, string> = {
  supported: "지원",
  conditional: "조건부",
  manual: "수동 입력",
  not_supported: "미지원",
  "n/a": "해당 없음",
};

export function ProviderCards({ providers }: { providers: ProviderStatus[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {providers.map((p) => (
        <Card key={p.provider_id} aria-label={p.label}>
          <div className="flex items-start justify-between gap-2">
            <CardTitle>{p.label}</CardTitle>
            <StatusBadge status={p.is_mock ? "mock" : p.source_kind} />
          </div>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted-foreground">상태</dt>
            <dd>{STATE_LABEL[p.state] ?? p.state}</dd>
            <dt className="text-muted-foreground">실행 모드</dt>
            <dd className="font-mono text-xs leading-5">{p.execution_mode}</dd>
            {p.selected_model && (
              <>
                <dt className="text-muted-foreground">작명 모델</dt>
                <dd className="break-all">{p.selected_model}</dd>
              </>
            )}
            <dt className="text-muted-foreground">마지막 확인</dt>
            <dd>{p.last_checked_at ?? "확인 불가"}</dd>
          </dl>
          <CardDescription className="mt-3">{p.message}</CardDescription>
          <table className="mt-3 w-full text-xs">
            <caption className="sr-only">{p.label} 지원 기능</caption>
            <tbody>
              {Object.entries(p.capabilities).map(([cap, level]) => (
                <tr key={cap} className="border-t border-border">
                  <th scope="row" className="py-1 text-left font-normal text-muted-foreground">
                    {CAP_LABEL[cap] ?? cap}
                  </th>
                  <td className="py-1 text-right">{LEVEL_LABEL[level] ?? level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}
    </div>
  );
}

export function ProviderError({ code, message, onRetry }: { code: string; message: string; onRetry: () => void }) {
  return (
    <Card role="alert" className="border-danger">
      <CardTitle>AI 연결 정보를 불러오지 못했습니다</CardTitle>
      <CardDescription className="mt-1">
        {message} <span className="font-mono">({code})</span>
      </CardDescription>
      <p className="mt-2 text-sm">AI 없이도 규칙 기반 작명·분석은 계속 사용할 수 있습니다.</p>
      <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
        다시 시도
      </Button>
    </Card>
  );
}

const defaultLoad = () => apiFetch<ProviderStatus[]>("ai/providers");

export function ProviderList({ load = defaultLoad }: {
  load?: () => Promise<ApiResult<ProviderStatus[]>>;
}) {
  const [result, setResult] = useState<ApiResult<ProviderStatus[]> | null>(null);
  const refresh = useCallback(() => {
    setResult(null);
    load().then(setResult);
  }, [load]);
  useEffect(refresh, [refresh]);

  if (!result) return <p aria-busy="true" className="text-sm text-muted-foreground">연결 상태 확인 중…</p>;
  if (!result.ok) return <ProviderError code={result.error.code} message={result.error.message} onRetry={refresh} />;
  return (
    <div className="space-y-3">
      {result.warnings.map((w) => (
        <p key={w.code} className="rounded-md border border-mock px-3 py-2 text-sm text-mock">
          {w.message}
        </p>
      ))}
      <ProviderCards providers={result.data} />
    </div>
  );
}
