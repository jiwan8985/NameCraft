"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const sections = [
  { href: "/ai/usage", label: "사용량 요약" },
  { href: "/ai/analytics", label: "모델별 분석" },
  { href: "/ai/sessions", label: "요청 기록" },
  { href: "/ai/providers", label: "모델 추천" },
  { href: "/ai/settings", label: "사용량 설정" },
];

export default function AILayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return (
    <div className="space-y-5">
      <nav aria-label="AI 메뉴" className="flex flex-wrap gap-1 rounded-xl border border-border bg-card p-1.5">
        {sections.map(({ href, label }) => (
          <Link key={href} href={href} aria-current={path === href ? "page" : undefined}
                className={cn("rounded-full px-3 py-2 text-sm transition",
                              path === href ? "bg-primary-soft font-semibold text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
            {label}
          </Link>
        ))}
      </nav>
      {children}
    </div>
  );
}
