"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { RankedItem } from "@/lib/types";

export function useCandidates(projectId: string) {
  const [items, setItems] = useState<RankedItem[]>([]);
  const reload = () => apiFetch<{ items: RankedItem[] }>(`projects/${projectId}/candidates`).then((r) => r.ok && setItems(r.data.items));
  useEffect(() => { reload(); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);
  return { items, reload };
}

export function ProjectNav({ projectId }: { projectId: string }) {
  const path = usePathname();
  const links = [["recommendations", "이름 후보"], ["scenario", "출생정보·사주"], ["reports", "보고서"]];
  return (
    <nav aria-label="프로젝트 메뉴" className="flex flex-wrap gap-1 rounded-xl border border-border bg-card p-1.5 text-sm">
      {links.map(([key, label]) => {
        const route = key === "recommendations" ? `/projects/${projectId}/recommendations` : `/${key}`;
        const current = route === path;
        return (
          <Link key={key} aria-current={current ? "page" : undefined}
                className={cn("rounded-full px-3 py-2 transition", current ? "bg-primary-soft font-semibold text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}
                href={key === "recommendations" ? route : `${route}?project=${projectId}`}>{label}</Link>
        );
      })}
    </nav>
  );
}
