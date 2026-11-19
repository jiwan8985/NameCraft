"use client";

import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { apiFetch, type ApiResult } from "@/lib/api";

export type AdminData = {
  summary: Record<string, number | Record<string, number>>;
  sources: { id: string; name: string; authority: string; license: string | null; status: string; notes: string | null }[];
  releases: { id: string; description: string | null; checksums: Record<string, string>; is_sample: boolean; created_at: string | null }[];
};

const SUMMARY_LABELS: Record<string, string> = {
  hanja_characters: "한자",
  hanja_readings: "독음",
  modern_stroke_counts: "현대 필획",
  original_stroke_counts: "성명학 원획",
  official_rules: "공식 인명용 한자 규칙",
  official_rules_sample: "샘플 규칙",
  surnames: "성씨",
  surnames_provisional: "임시 성씨",
  surnames_conflict: "성씨 충돌",
};

const SOURCE_STATUS: Record<string, string> = {
  candidate: "후보(미검토)",
  license_review: "이용조건 검토 중",
  approved: "승인",
  ingested: "적재됨",
  rejected: "제외",
};

export function AdminDataView({ data }: { data: AdminData }) {
  const s = data.summary;
  const official = Number(s.official_rules ?? 0);
  return (
    <div className="space-y-6">
      {official === 0 && (
        <p role="status" className="rounded-md border border-warn px-3 py-2 text-sm text-warn">
          공식 인명용 한자표가 적재되지 않았습니다. 모든 한자의 법적 허용 여부는 &lsquo;판정 불가&rsquo;로 표시됩니다.
        </p>
      )}
      <section aria-labelledby="summary-h">
        <h2 id="summary-h" className="mb-2 text-lg font-semibold">데이터 현황</h2>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {Object.entries(SUMMARY_LABELS).map(([k, label]) => (
            <Card key={k} className="p-3">
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="mt-1 text-xl font-semibold tabular-nums">{Number(s[k] ?? 0).toLocaleString("ko-KR")}</dd>
            </Card>
          ))}
        </dl>
      </section>

      <section aria-labelledby="sources-h">
        <h2 id="sources-h" className="mb-2 text-lg font-semibold">출처</h2>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-muted text-left text-xs text-muted-foreground">
              <tr><th className="p-2">ID</th><th className="p-2">이름</th><th className="p-2">권위</th><th className="p-2">라이선스</th><th className="p-2">상태</th></tr>
            </thead>
            <tbody>
              {data.sources.map((src) => (
                <tr key={src.id} className="border-t border-border align-top">
                  <td className="p-2 font-mono text-xs">{src.id}</td>
                  <td className="p-2">{src.name}</td>
                  <td className="p-2 text-xs">{src.authority}</td>
                  <td className="p-2 text-xs">{src.license ?? "미확인"}</td>
                  <td className="p-2 text-xs">{SOURCE_STATUS[src.status] ?? src.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="releases-h">
        <h2 id="releases-h" className="mb-2 text-lg font-semibold">데이터 버전</h2>
        <ul className="space-y-2">
          {data.releases.map((r) => (
            <li key={r.id}>
              <Card className="p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <CardTitle className="font-mono text-sm">{r.id}</CardTitle>
                  {r.is_sample && <StatusBadge status="demo" />}
                </div>
                <CardDescription className="mt-1">{r.description}</CardDescription>
                {Object.entries(r.checksums).map(([f, sum]) => (
                  <p key={f} className="mt-1 break-all font-mono text-xs text-muted-foreground">{f} sha256:{sum}</p>
                ))}
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

const defaultLoad = () => apiFetch<AdminData>("admin/data");

export function AdminData({ load = defaultLoad }: { load?: () => Promise<ApiResult<AdminData>> }) {
  const [result, setResult] = useState<ApiResult<AdminData> | null>(null);
  const refresh = useCallback(() => {
    setResult(null);
    load().then(setResult);
  }, [load]);
  useEffect(refresh, [refresh]);

  if (!result) return <p aria-busy="true" className="text-sm text-muted-foreground">불러오는 중…</p>;
  if (!result.ok)
    return (
      <Card role="alert" className="border-danger">
        <CardTitle>데이터 현황을 불러오지 못했습니다</CardTitle>
        <CardDescription className="mt-1">{result.error.message} ({result.error.code})</CardDescription>
        <Button variant="outline" size="sm" className="mt-3" onClick={refresh}>다시 시도</Button>
      </Card>
    );
  return <AdminDataView data={result.data} />;
}
