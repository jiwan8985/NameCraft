"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ProjectNav, useCandidates } from "@/components/collab/use-project";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Field, Input, Notice } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";
import type { Project } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
const KIND_LABEL: Record<string, string> = { project_summary: "프로젝트 요약", name_detail: "이름 상세", comparison: "후보 비교" };

function ProjectReports({ projectId }: { projectId: string }) {
  const { items } = useCandidates(projectId);
  const [sel, setSel] = useState<string[]>([]);
  const [list, setList] = useState<any[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => apiFetch<any[]>(`projects/${projectId}/reports`).then((r) => r.ok && setList(r.data)), [projectId]);
  useEffect(() => { load(); }, [load]);
  async function make(kind: string) {
    const r = await postJson<any>("reports", { project_id: projectId, kind, candidate_ids: kind === "project_summary" ? null : sel });
    if (!r.ok) return setMsg(r.error.message);
    window.open(`/reports/view?id=${r.data.id}`, "_blank");
    load();
  }
  async function del() {
    if (!confirm("이 프로젝트의 후보·평가·출생정보·업로드 자료를 모두 삭제합니다. 되돌릴 수 없습니다. 계속할까요?")) return;
    const r = await apiFetch(`projects/${projectId}`, { method: "DELETE" });
    setMsg(r.ok ? "삭제했습니다." : r.error.message);
  }
  return (
    <div className="space-y-4">
      <ProjectNav projectId={projectId} />
      {msg && <Notice role="status">{msg}</Notice>}
      <Card className="space-y-3">
        <CardTitle>보고서 만들기</CardTitle>
        <CardDescription>보고서는 생성 당시 데이터로 저장됩니다. 화면에서 인쇄 → &lsquo;PDF로 저장&rsquo;으로 PDF 를 만듭니다.</CardDescription>
        <div className="flex flex-wrap gap-2">{items.map((c) => (
          <label key={c.id} className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-sm">
            <input type="checkbox" checked={sel.includes(c.id!)} onChange={(e) => setSel((s) => e.target.checked ? [...s, c.id!].slice(0, 10) : s.filter((x) => x !== c.id))} />
            {c.full_hangul}</label>))}</div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => make("project_summary")}>프로젝트 요약</Button>
          <Button variant="outline" disabled={sel.length !== 1} onClick={() => make("name_detail")}>이름 상세 (1개 선택)</Button>
          <Button variant="outline" disabled={sel.length < 2} onClick={() => make("comparison")}>후보 비교 (2~10개)</Button>
        </div>
      </Card>
      <Card className="space-y-2">
        <CardTitle>내보내기</CardTitle>
        <div className="flex flex-wrap gap-3 text-sm">
          <a className="underline" href={`/api/proxy/projects/${projectId}/candidates.csv`}>후보 목록 CSV</a>
          <a className="underline" href={`/api/proxy/projects/${projectId}/export`}>프로젝트 JSON(백업)</a>
        </div>
        <CardDescription>JSON 에는 무결성 확인값이 들어 있습니다. 업로드 원본 파일·AI 실행 설정·사용량 기록은 포함하지 않습니다.</CardDescription>
        <Button size="sm" variant="ghost" onClick={del}>이 프로젝트 완전 삭제</Button>
      </Card>
      {list.length > 0 && (
        <Card><CardTitle>보고서 기록</CardTitle>
          <ul className="mt-2 text-sm">{list.map((r) => <li key={r.id}><Link className="underline" href={`/reports/view?id=${r.id}`} target="_blank">{KIND_LABEL[r.kind]}</Link> · {r.created_at.slice(0, 16)} · 랭킹 {r.versions.ranking}</li>)}</ul></Card>
      )}
    </div>
  );
}

function GlobalBackup() {
  const [msg, setMsg] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState("");
  async function restore(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    let doc: any;
    try { doc = JSON.parse(await f.text()); } catch { return setMsg("JSON 파일이 아닙니다."); }
    const r = doc.schema === "namecraft.backup" ? await postJson<any>("backup/restore", doc) : await postJson<any>("projects/import", doc);
    setMsg(r.ok ? "새 프로젝트로 복원했습니다. 대시보드에서 확인하세요." : `${r.error.message}`);
  }
  async function wipe() {
    const r = await postJson<any>("data/delete-all", { confirm: confirmText });
    setMsg(r.ok ? `사용자 데이터를 삭제했습니다(프로젝트 ${r.data.deleted_projects}개).` : r.error.message);
  }
  return (
    <Card className="space-y-3">
      <CardTitle>백업·복원·전체 삭제</CardTitle>
      {msg && <Notice role="status">{msg}</Notice>}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <a className="underline" href="/api/proxy/backup">전체 백업 받기(JSON)</a>
        <label className="inline-flex items-center gap-2">복원: <input type="file" accept="application/json,.json" onChange={restore} /></label>
      </div>
      <CardDescription>복원은 항상 새 프로젝트로 만들며 기존 데이터를 덮어쓰지 않습니다. 확인값이 맞지 않으면 복원하지 않습니다.</CardDescription>
      <div className="flex flex-wrap items-end gap-2">
        <Field label="전체 삭제 확인 — DELETE ALL 입력" htmlFor="wipe"><Input id="wipe" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} /></Field>
        <Button variant="outline" disabled={confirmText !== "DELETE ALL"} onClick={wipe}>사용자 데이터 전체 삭제</Button>
      </div>
    </Card>
  );
}

export function ReportsView() {
  const pid = useSearchParams().get("project");
  const [projects, setProjects] = useState<Project[]>([]);
  useEffect(() => { if (!pid) apiFetch<Project[]>("projects").then((r) => r.ok && setProjects(r.data)); }, [pid]);
  return (
    <div className="space-y-4">
      {pid ? <ProjectReports projectId={pid} /> : (
        <Card><CardTitle>프로젝트 선택</CardTitle>
          <ul className="mt-2 text-sm">{projects.map((p) => <li key={p.id}><Link className="hover:underline" href={`/reports?project=${p.id}`}>{p.title}</Link></li>)}</ul></Card>
      )}
      <GlobalBackup />
    </div>
  );
}
