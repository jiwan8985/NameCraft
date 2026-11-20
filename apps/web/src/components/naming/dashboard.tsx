"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, FolderHeart, Heart, ListChecks, QrCode, Search, Sprout, Trash2, X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Notice } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";
import type { Project } from "@/lib/types";

const journey = [
  { title: "이름 후보 찾기", description: "성과 좋아하는 느낌을 알려 주세요. 출생일이 정해지기 전에도 시작할 수 있어요.", icon: Sprout },
  { title: "후보 비교하기", description: "마음에 드는 이름을 담고, 뜻과 발음을 나란히 비교해 보세요.", icon: ListChecks },
  { title: "출생정보로 사주 살펴보기", description: "예정일이나 실제 출생일로 한자 이름 후보를 살펴볼 수 있어요.", icon: BookOpen },
];

export function Dashboard({ desktopQR }: { desktopQR: boolean }) {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState("");
  async function deleteProject(project: Project) {
    if (!window.confirm(`‘${project.title}’ 프로젝트와 저장된 후보를 삭제할까요?`)) return;
    setDeleting(project.id);
    setDeleteError("");
    const result = await apiFetch(`projects/${project.id}`, { method: "DELETE" });
    setDeleting(null);
    if (!result.ok) return setDeleteError(result.error.message);
    setProjects((current) => current?.filter((item) => item.id !== project.id) ?? null);
  }

  function loadProjects() {
    setError(null);
    apiFetch<Project[]>("projects").then((result) => {
      if (result.ok) setProjects(result.data);
      else setError(result.error.code === "pairing_required" ? result.error.message : "프로젝트를 불러오지 못했어요.");
    });
  }

  useEffect(loadProjects, []);

  return (
    <div className="space-y-10 sm:space-y-14">
      <section className="naming-hero relative isolate overflow-hidden rounded-[2rem] border border-border px-6 py-10 sm:px-12 sm:py-16 lg:px-16">
        <div className="relative z-10 max-w-xl">
          <p className="mb-5 flex items-center gap-2 text-sm font-semibold text-primary">
            <Heart className="size-4" aria-hidden="true" /> 출산을 준비하는 가족을 위한 작명
          </p>
          <h1 className="naming-title text-[clamp(2.2rem,6vw,4.5rem)] leading-[1.16] font-semibold tracking-[-0.08em]">
            우리 아기에게<br />불러 주고 싶은 이름
          </h1>
          <p className="mt-5 max-w-sm leading-relaxed text-muted-foreground">
            첫 이름을 찾아보는 순간부터 가족이 함께 결정하는 날까지, 마음에 드는 이름을 하나씩 모아 보세요.
          </p>
          <div className="mt-7 flex flex-wrap gap-2.5">
            <Link href="/projects/new" className={buttonVariants({ size: "lg" })}>아기 이름 짓기</Link>
            <Link href="/names/analyze" className={buttonVariants({ size: "lg", variant: "outline" })}>
              <Search className="size-4" aria-hidden="true" /> 생각해 둔 이름 분석
            </Link>
          </div>
        </div>
        <div className="naming-hero-art pointer-events-none absolute inset-y-0 right-0 hidden w-[42%] items-center justify-center lg:flex" aria-hidden="true">
          <span className="naming-hero-sheet naming-hero-sheet-back" />
          <span className="naming-hero-sheet naming-hero-sheet-front"><Sprout className="size-7" />이름</span>
        </div>
      </section>

      <div>
        <Button variant="outline" popoverTarget="mobile-qr-popover">
          <QrCode className="size-4" aria-hidden="true" /> 휴대폰에서 열기
        </Button>
        <section id="mobile-qr-popover" popover="auto" aria-labelledby="mobile-qr-title"
                 className="mobile-qr-popover max-h-[calc(100dvh-2rem)] overflow-auto rounded-[1.75rem] border border-border bg-card p-0 text-foreground shadow-2xl">
          <div className="relative rounded-t-[1.75rem] bg-primary-soft px-6 pt-6 pb-5 pr-14">
            <div className="mb-3 grid size-10 place-items-center rounded-xl bg-card text-primary">
              <QrCode className="size-5" aria-hidden="true" />
            </div>
            <h2 id="mobile-qr-title" className="text-xl font-semibold tracking-tight">휴대폰에서 이어서 작명하기</h2>
            <Button variant="ghost" size="icon" className="absolute top-4 right-4" aria-label="닫기"
                    popoverTarget="mobile-qr-popover" popoverTargetAction="hide">
              <X className="size-5" aria-hidden="true" />
            </Button>
          </div>
          {desktopQR ? (
            <iframe src="http://127.0.0.1:3001/mobile?embed=1" loading="lazy" title="휴대폰 접속 QR"
                    className="block h-[17.25rem] w-full border-0" />
          ) : (
            <p className="p-6 text-sm text-muted-foreground">PC에서 NameCraft 명령 메뉴의 1번으로 실행하면 QR을 볼 수 있어요.</p>
          )}
          <div className="px-6 pb-5 text-center">
            {desktopQR && <p className="text-sm text-muted-foreground">PC와 같은 Wi-Fi에서 휴대폰 카메라로 찍어 주세요.</p>}
          </div>
        </section>
      </div>

      <section aria-labelledby="saved-projects" className="space-y-4">
        <h2 id="saved-projects" className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <FolderHeart className="size-5 text-primary" aria-hidden="true" /> 저장한 작명 프로젝트
        </h2>
        {error && (
          <Notice tone="danger" role="alert">
            {error} <button type="button" onClick={loadProjects} className="ml-1 font-semibold underline">다시 시도</button>
          </Notice>
        )}
        {deleteError && <Notice tone="danger" role="alert">{deleteError}</Notice>}
        {!projects && !error && <p role="status" className="text-muted-foreground">프로젝트를 불러오는 중이에요.</p>}
        {projects?.length === 0 && <Card className="text-muted-foreground">첫 프로젝트를 시작하면 여기에서 이어서 이름을 고를 수 있어요.</Card>}
        {!!projects?.length && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <Card key={project.id} className="flex h-full items-start gap-2 transition hover:border-primary">
                <Link href={`/projects/${project.id}/recommendations`} className="min-w-0 flex-1 rounded-md">
                  <p className="break-words font-semibold">{project.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{project.surname_hangul}{project.surname_hanja ? ` · ${project.surname_hanja}` : ""} · {project.created_at.slice(0, 10)}</p>
                  <p className="mt-3 text-sm font-semibold text-primary">이름 후보 이어 보기</p>
                </Link>
                <Button variant="ghost" size="icon" className="shrink-0 hover:text-danger"
                        aria-label={`${project.title} 삭제`} disabled={deleting !== null} onClick={() => deleteProject(project)}>
                  <Trash2 className="size-4" aria-hidden="true" />
                </Button>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section aria-label="아기 이름을 고르는 과정" className="grid gap-5 border-t border-border pt-7 sm:grid-cols-3 sm:gap-8">
        {journey.map(({ title, description, icon: Icon }) => (
          <div key={title} className="flex items-start gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary"><Icon className="size-5" aria-hidden="true" /></span>
            <div>
              <h2 className="font-semibold">{title}</h2>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{description}</p>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
