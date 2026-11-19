"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { FamilyView } from "@/components/collab/family-view";
import { FinalizeView } from "@/components/collab/finalize-view";
import { ScenarioView } from "@/components/collab/scenario-view";
import { TournamentView } from "@/components/collab/tournament-view";
import { Card, CardTitle } from "@/components/ui/card";
import { Notice } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";
import type { Project } from "@/lib/types";

const VIEWS = { scenario: ScenarioView, family: FamilyView, tournament: TournamentView, finalize: FinalizeView };

/** ?project= 가 없으면 프로젝트 선택 목록을 보여준다. */
export function ProjectGate({ view }: { view: keyof typeof VIEWS }) {
  const sp = useSearchParams();
  const path = usePathname();
  const pid = sp.get("project");
  const [projects, setProjects] = useState<Project[] | null>(null);
  useEffect(() => {
    if (!pid) apiFetch<Project[]>("projects").then((r) => r.ok && setProjects(r.data));
  }, [pid]);
  if (pid) {
    const View = VIEWS[view];
    return <View projectId={pid} />;
  }
  return (
    <Card className="space-y-2">
      <CardTitle>프로젝트 선택</CardTitle>
      {projects?.length === 0 && <Notice>먼저 <Link href="/projects/new" className="underline">새 프로젝트</Link>를 만드세요.</Notice>}
      <ul className="space-y-1 text-sm">
        {projects?.map((p) => <li key={p.id}><Link className="hover:underline" href={`${path}?project=${p.id}`}>{p.title}</Link></li>)}
      </ul>
    </Card>
  );
}

