"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Notice } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";
import type { Project } from "@/lib/types";

export function Dashboard() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    apiFetch<Project[]>("projects").then((r) => (r.ok ? setProjects(r.data) : setError(r.error.message)));
  }, []);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Link href="/projects/new" className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground">새 작명 프로젝트</Link>
        <Link href="/names/analyze" className="rounded-md border border-border px-4 py-2 text-sm">이름 분석하기</Link>
      </div>
      {error && <Notice tone="danger" role="alert">{error}</Notice>}
      {projects && projects.length === 0 && <p className="text-sm text-muted-foreground">아직 프로젝트가 없습니다.</p>}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {projects?.map((p) => (
          <Card key={p.id}>
            <CardTitle><Link href={`/projects/${p.id}/recommendations`} className="hover:underline">{p.title}</Link></CardTitle>
            <CardDescription className="mt-1">성씨 {p.surname_hangul}{p.surname_hanja ? `(${p.surname_hanja})` : ""} · {p.created_at.slice(0, 10)}</CardDescription>
          </Card>
        ))}
      </div>
    </div>
  );
}
