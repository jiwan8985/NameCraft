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
  const links = [["recommendations", "추천"], ["scenario", "시나리오"], ["family", "가족 평가"], ["tournament", "토너먼트"], ["finalize", "결선"]];
  return (
    <nav aria-label="프로젝트 메뉴" className="flex flex-wrap gap-2 text-sm">
      {links.map(([k, l]) => (
        <Link key={k} className="rounded-md border border-border px-3 py-1 hover:bg-muted"
              href={k === "recommendations" ? `/projects/${projectId}/recommendations` : `/${k}?project=${projectId}`}>{l}</Link>
      ))}
    </nav>
  );
}
