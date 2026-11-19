"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Input, Notice, Select } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";
import type { Warning } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
const FIELDS = [
  ["name_hangul", "이름(한글, 성 포함)"], ["name_hanja", "이름(한자, 성 포함)"], ["gyeok.won", "원격"], ["gyeok.hyeong", "형격"],
  ["gyeok.i", "이격"], ["gyeok.jeong", "정격"], ["luck.won", "원격 길흉(good/half/bad)"], ["saju_pillars", "사주 명식(예: 丙午 辛丑 甲午 己巳)"],
  ["birth_date", "출생일(YYYY-MM-DD)"], ["birth_time", "출생 시각(HH:MM)"], ["birth_calendar", "달력(solar/lunar)"],
] as const;
const RESULT: Record<string, { label: string; status: string }> = {
  match: { label: "일치", status: "official" }, numeric_difference: { label: "숫자 차이", status: "review" },
  formula_difference: { label: "공식·옵션 차이", status: "conflict" }, source_difference: { label: "출처·학파 차이", status: "traditional" },
  not_comparable: { label: "비교 불가", status: "unknown" },
};
const REVIEW: Record<string, string> = { pending: "검토 전", accepted: "확인", corrected: "수정됨", rejected: "제외" };

export function ImportsView() {
  const projectId = useSearchParams().get("project");
  const [docs, setDocs] = useState<any[]>([]);
  const [doc, setDoc] = useState<any>(null);
  const [warn, setWarn] = useState<Warning[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [edit, setEdit] = useState<Record<string, string>>({});
  const [manual, setManual] = useState({ field: "gyeok.won", value: "" });

  const loadList = useCallback(() => apiFetch<any[]>(`imports${projectId ? `?project_id=${projectId}` : ""}`)
    .then((r) => r.ok && setDocs(r.data)), [projectId]);
  const open = useCallback(async (id: string) => {
    const r = await apiFetch<any>(`imports/${id}`);
    if (r.ok) { setDoc(r.data); setWarn(r.warnings); } else setMsg(r.error.message);
  }, []);
  useEffect(() => { loadList(); }, [loadList]);

  async function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    if (projectId) fd.set("project_id", projectId);
    const r = await apiFetch<any>("imports", { method: "POST", body: fd });
    if (!r.ok) return setMsg(r.error.message);
    setMsg(null); setDoc(r.data); setWarn(r.warnings); loadList();
  }
  async function review(id: string, status: string) {
    const r = await postJson(`assertions/${id}`, { review_status: status, corrected_value: edit[id] }, "PATCH");
    if (!r.ok) return setMsg(r.error.message);
    open(doc.id);
  }
  async function addManual() {
    const r = await postJson(`imports/${doc.id}/assertions`, manual);
    if (!r.ok) return setMsg(r.error.message);
    setManual((m) => ({ ...m, value: "" })); open(doc.id);
  }
  async function crosscheck() {
    const r = await postJson<any>(`imports/${doc.id}/crosscheck`, {});
    if (!r.ok) return setMsg(r.error.message);
    setWarn(r.warnings); open(doc.id);
  }
  async function remove() {
    if (!confirm("원본 파일과 추출값을 모두 삭제합니다. 계속할까요?")) return;
    const r = await apiFetch(`imports/${doc.id}`, { method: "DELETE" });
    if (!r.ok) return setMsg(r.error.message);
    setDoc(null); loadList();
  }

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={upload} className="flex flex-wrap items-end gap-2">
          <Field label="작명소 자료 올리기" htmlFor="file" hint="PDF·PNG·JPEG·WEBP·텍스트·CSV, 10MB 이하. 문서 내용은 외부로 보내지 않습니다.">
            <input id="file" name="file" type="file" required accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.csv" className="text-sm" />
          </Field>
          <Button type="submit">올리기</Button>
        </form>
      </Card>
      {msg && <Notice tone="danger" role="alert">{msg}</Notice>}
      {docs.length > 0 && (
        <Card><CardTitle>올린 자료</CardTitle>
          <ul className="mt-2 text-sm">{docs.map((d) => <li key={d.id}><button className="hover:underline" onClick={() => open(d.id)}>{d.filename}</button> · {d.kind} · {d.status} · 보관 {d.retention_until?.slice(0, 10)}까지</li>)}</ul></Card>
      )}
      {doc && (
        <>
          {warn.map((w) => <Notice key={w.code} tone="warn">{w.message}</Notice>)}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="space-y-2">
              <CardTitle>원본 — {doc.filename}</CardTitle>
              {doc.kind === "image" ? <img src={`/api/proxy/imports/${doc.id}/file`} alt="올린 자료 원본" className="max-h-[32rem] w-full object-contain" />
                : doc.kind === "pdf" && !doc.extracted_text ? <a className="underline" href={`/api/proxy/imports/${doc.id}/file`} target="_blank" rel="noreferrer">PDF 원본 열기</a>
                : <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">{doc.extracted_text}</pre>}
              <CardDescription>sha256 {doc.sha256.slice(0, 16)}… · {doc.extraction_method}</CardDescription>
            </Card>
            <Card className="space-y-2">
              <CardTitle>추출값 검토</CardTitle>
              <CardDescription>원문과 비교해 확인·수정·제외하세요. 확인된 값만 교차검증에 쓰입니다.</CardDescription>
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted-foreground"><tr><th>항목</th><th>값</th><th>원문</th><th>상태</th><th /></tr></thead>
                <tbody>{doc.assertions.map((a: any) => (
                  <tr key={a.id} className="border-t border-border align-top">
                    <td className="py-1 text-xs">{a.field}</td>
                    <td><Input aria-label={`${a.field} 수정값`} defaultValue={a.effective_value} onChange={(e) => setEdit((x) => ({ ...x, [a.id]: e.target.value }))} className="py-1" /></td>
                    <td className="text-xs text-muted-foreground">{a.raw_text ?? "직접 입력"}</td>
                    <td className="text-xs">{REVIEW[a.review_status]}</td>
                    <td><div className="flex gap-1">
                      <Button size="sm" variant="outline" onClick={() => review(a.id, edit[a.id] && edit[a.id] !== a.value ? "corrected" : "accepted")}>확인</Button>
                      <Button size="sm" variant="ghost" onClick={() => review(a.id, "rejected")}>제외</Button></div></td>
                  </tr>))}</tbody>
              </table>
              <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
                <Field label="직접 입력 — 항목" htmlFor="mf"><Select id="mf" value={manual.field} onChange={(e) => setManual((m) => ({ ...m, field: e.target.value }))}>
                  {FIELDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Select></Field>
                <Field label="값" htmlFor="mv"><Input id="mv" value={manual.value} onChange={(e) => setManual((m) => ({ ...m, value: e.target.value }))} /></Field>
                <Button variant="outline" disabled={!manual.value} onClick={addManual}>추가</Button>
              </div>
              <div className="flex justify-between">
                <Button onClick={crosscheck}>교차검증</Button>
                <Button variant="ghost" onClick={remove}>자료 삭제</Button>
              </div>
            </Card>
          </div>
          {doc.crosscheck && (
            <Card className="space-y-2">
              <CardTitle>교차검증 결과</CardTitle>
              <CardDescription>{doc.crosscheck.summary.note}</CardDescription>
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted-foreground"><tr><th>항목</th><th>문서</th><th>결과</th><th>설명</th></tr></thead>
                <tbody>{doc.crosscheck.items.map((i: any, n: number) => (
                  <tr key={n} className="border-t border-border align-top">
                    <td className="py-1">{i.item}</td><td className="text-xs">{typeof i.doc === "object" ? JSON.stringify(i.doc) : String(i.doc)}</td>
                    <td><StatusBadge status={RESULT[i.result].status} /> <span className="text-xs">{RESULT[i.result].label}</span></td>
                    <td className="text-xs text-muted-foreground">{i.detail}</td></tr>))}</tbody>
              </table>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
