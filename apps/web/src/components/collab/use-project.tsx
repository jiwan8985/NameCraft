"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { RankedItem } from "@/lib/types";

export function useCandidates(projectId: string) {
  const [items, setItems] = useState<RankedItem[]>([]);
  const reload = () => apiFetch<{ items: RankedItem[] }>(`projects/${projectId}/candidates`).then((r) => r.ok && setItems(r.data.items));
  useEffect(() => { reload(); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);
  return { items, reload };
}

export function ProjectNav({ projectId }: { projectId: string }) {
  const links = [["recommendations", "후보"], ["scenario", "출생 시각"], ["family", "가족 의견"], ["tournament", "1:1 고르기"], ["finalize", "최종 결정"], ["reports", "보고서"]];
  return (
    <nav aria-label="프로젝트 메뉴" className="-mx-1 flex gap-1 overflow-x-auto rounded-full bg-muted p-1 text-sm">
      {links.map(([k, l]) => (
        <Link key={k} className="shrink-0 rounded-full px-3.5 py-1.5 text-muted-foreground transition hover:bg-card hover:text-foreground"
              href={k === "recommendations" ? `/projects/${projectId}/recommendations` : `/${k}?project=${projectId}`}>{l}</Link>
      ))}
    </nav>
  );
}
