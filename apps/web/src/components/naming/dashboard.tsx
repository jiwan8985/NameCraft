"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, FolderHeart, Search, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
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
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">안녕하세요 👋</h1>
        <p className="mt-1 text-muted-foreground">아이 이름, 차근차근 함께 정해 봐요.</p>
      </section>

      <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
        <Link href="/projects/new" className="group block">
          <Card className="flex h-full items-center gap-4 bg-gradient-to-br from-primary-soft to-card p-6 transition group-hover:shadow-md">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-primary text-primary-foreground"><Sparkles className="h-6 w-6" /></span>
            <div className="flex-1">
              <p className="text-lg font-semibold">새 이름 짓기</p>
              <p className="text-sm text-muted-foreground">성씨와 원하는 느낌만 알려 주세요</p>
            </div>
            <ArrowRight className="h-5 w-5 text-primary transition group-hover:translate-x-1" />
          </Card>
        </Link>
        <Link href="/names/analyze" className="group block">
          <Card className="flex h-full items-center gap-3 p-6 transition group-hover:shadow-md">
            <Search className="h-5 w-5 text-primary" />
            <div>
              <p className="font-semibold">이름 분석</p>
              <p className="text-sm text-muted-foreground">생각해 둔 이름 살펴보기</p>
            </div>
          </Card>
        </Link>
      </div>

      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><FolderHeart className="h-5 w-5 text-primary" /> 내 작명</h2>
        {error && <Notice tone="danger" role="alert">{error}</Notice>}
        {projects && projects.length === 0 && (
          <Card className="text-center text-sm text-muted-foreground">아직 없어요. 위의 &lsquo;새 이름 짓기&rsquo;로 시작해 보세요.</Card>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects?.map((p) => (
            <Link key={p.id} href={`/projects/${p.id}/recommendations`} className="group block">
              <Card className="transition group-hover:shadow-md">
                <p className="font-semibold">{p.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">{p.surname_hangul}{p.surname_hanja ? ` · ${p.surname_hanja}` : ""} · {p.created_at.slice(0, 10)}</p>
                <p className="mt-3 text-sm font-medium text-primary">후보 보기 →</p>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
