"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChartNoAxesColumn, Home, Search, Sparkles, Sprout } from "lucide-react";
import { cn } from "@/lib/utils";

export const PRIMARY_NAV = [
  { href: "/dashboard", label: "홈", icon: Home, match: ["/dashboard"] },
  { href: "/projects/new", label: "이름 짓기", icon: Sparkles, match: ["/projects", "/compare", "/scenario", "/family", "/tournament", "/finalize", "/names/", "/reports"] },
  { href: "/names/analyze", label: "이름 분석", icon: Search, match: ["/names/analyze"] },
  { href: "/ai/usage", label: "AI 사용량", icon: ChartNoAxesColumn, match: ["/ai"] },
];

export function TopNav() {
  const path = usePathname() ?? "";
  const active = (m: string[]) => m.some((x) => path === x || path.startsWith(x.endsWith("/") ? x : `${x}/`));
  return (
    <header data-app-header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-1 px-4">
        <Link href="/dashboard" className="mr-2 flex items-center gap-2 font-semibold">
          <span className="grid size-8 place-items-center rounded-xl bg-primary text-primary-foreground" aria-hidden="true"><Sprout className="size-5" /></span>
          <span className="max-[360px]:sr-only">NameCraft</span>
        </Link>
        <nav aria-label="주요 메뉴" className="ml-auto flex items-center gap-0.5 sm:gap-1">
          {PRIMARY_NAV.map(({ href, label, icon: Icon, match }) => {
            const isCurrent = path === "/names/analyze" ? href === path : active(match);
            return (
              <Link key={href} href={href} aria-current={isCurrent ? "page" : undefined}
                    aria-label={label}
                    className={cn("flex items-center gap-1.5 rounded-full px-2 py-2 text-xs sm:text-sm transition sm:px-3",
                                  isCurrent ? "bg-primary-soft font-medium text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
                <Icon className="hidden size-4 sm:block max-[480px]:block" aria-hidden="true" />
                <span className={cn(href !== "/ai/usage" && "max-[480px]:sr-only")}>{label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
