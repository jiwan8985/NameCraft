"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Notice } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
const TONE: Record<string, string> = { pass: "text-ok", warn: "text-warn", recheck: "text-warn", fail: "text-danger" };
const LABEL: Record<string, string> = { pass: "통과", warn: "확인 권장", recheck: "공식 재확인 필요", fail: "수정 필요" };

/** 출생신고 준비 모드 (기획서 §14) — 결정된 이름 기준. 확정 완료로 표시하지 않는다. */
export function RegistrationCheck({ projectId, refreshKey }: { projectId: string; refreshKey: number }) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    apiFetch<any>(`projects/${projectId}/finalize-check`).then((r) => { if (r.ok) { setD(r.data); setErr(null); } else setErr(r.error.message); });
  }, [projectId, refreshKey]);
  if (err) return <Notice>{err}</Notice>;
  if (!d) return null;
  return (
    <Card className="space-y-3 print:border-0 print:shadow-none">
      <div className="flex items-start justify-between gap-2">
        <div>
          <CardTitle>출생신고 준비 점검 — {d.name.full} {d.name.full_hanja ?? ""}</CardTitle>
          <p className={`mt-1 text-sm font-semibold ${d.overall === "fix_required" ? "text-danger" : "text-warn"}`}>{d.overall_label}</p>
        </div>
        <Button size="sm" variant="outline" className="print:hidden" onClick={() => window.print()}>인쇄</Button>
      </div>
      <ul className="space-y-1 text-sm">{d.checks.map((c: any) => (
        <li key={c.id}><span className={`mr-2 font-medium ${TONE[c.status]}`}>[{LABEL[c.status]}]</span>{c.message}</li>))}</ul>
      {d.characters.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted-foreground"><tr><th>글자</th><th>한글</th><th>독음 일치</th><th>공식 판정</th><th>허용 독음(공식)</th></tr></thead>
          <tbody>{d.characters.map((c: any) => (
            <tr key={c.position} className="border-t border-border"><td>{c.hanja} <span className="text-xs text-muted-foreground">{c.codepoint}</span></td><td>{c.hangul}</td>
              <td>{c.reading_match ? "예" : "아니오"}</td><td>{c.official}</td><td>{c.allowed_readings.join(", ") || "—"}</td></tr>))}</tbody>
        </table>
      )}
      <p className="text-xs text-muted-foreground">데이터 기준: {d.data_basis.official_data_loaded ? `공식 자료 확인일 ${d.data_basis.checked_at?.slice(0, 10)} · 고시 ${d.data_basis.effective_date ?? "미상"}` : "공식 인명용 한자표 미적재"}</p>
      <div>
        <p className="text-sm font-medium">직접 확인할 체크리스트</p>
        <ul className="list-disc pl-5 text-sm">{d.checklist.map((x: string) => <li key={x}>{x}</li>)}</ul>
      </div>
      <ul className="text-sm">{d.official_links.map((l: any) => <li key={l.url}><a className="underline" href={l.url} target="_blank" rel="noreferrer">{l.label}</a></li>)}</ul>
      <CardDescription>{d.disclaimer}</CardDescription>
    </Card>
  );
}
