"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Search, Settings, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

/** 주요 메뉴 4개. 나머지 기능은 설정 › 더 많은 기능 */
export const PRIMARY_NAV = [
  { href: "/dashboard", label: "홈", icon: Home, match: ["/dashboard"] },
  { href: "/projects/new", label: "이름 짓기", icon: Sparkles, match: ["/projects", "/compare", "/scenario", "/family", "/tournament", "/finalize", "/names/"] },
  { href: "/names/analyze", label: "이름 분석", icon: Search, match: ["/names/analyze"] },
  { href: "/settings", label: "설정", icon: Settings, match: ["/settings", "/ai", "/admin", "/imports", "/reports"] },
];

export function TopNav() {
  const path = usePathname() ?? "";
  const active = (m: string[]) => m.some((x) => path === x || path.startsWith(x));
  return (
    <header data-app-header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-1 px-4">
        <Link href="/dashboard" className="mr-2 flex items-center gap-2 font-semibold">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-primary" aria-hidden="true" />
          NameCraft
        </Link>
        <nav aria-label="주요 메뉴" className="ml-auto flex items-center gap-0.5 sm:gap-1">
          {PRIMARY_NAV.map(({ href, label, icon: Icon, match }) => (
            <Link key={href} href={href} aria-current={active(match) ? "page" : undefined}
                  aria-label={label}
                  className={cn("flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-sm transition sm:px-3",
                                active(match) ? "bg-primary-soft font-medium text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
              <Icon className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">{label}</span>
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
