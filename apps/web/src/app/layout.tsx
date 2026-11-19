import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";
import { GROUP_LABELS, ROUTES, type RouteDef } from "@/lib/routes";

export const metadata: Metadata = {
  title: "NameCraft AI",
  description: "검증 가능한 개인용 AI 작명 플랫폼",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

function Nav() {
  const groups = Object.keys(GROUP_LABELS) as RouteDef["group"][];
  return (
    <nav aria-label="주요 메뉴" className="flex gap-6 overflow-x-auto text-sm md:block md:space-y-5">
      {groups.map((g) => (
        <div key={g} className="shrink-0">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{GROUP_LABELS[g]}</p>
          <ul className="flex gap-3 md:block md:space-y-0.5">
            {ROUTES.filter((r) => r.group === g && r.nav).map((r) => (
              <li key={r.path}>
                <Link href={r.path} className="block whitespace-nowrap rounded-md py-1 md:px-2 md:hover:bg-muted">
                  {r.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen antialiased">
        <div className="mx-auto flex max-w-7xl flex-col md:flex-row">
          <aside className="border-b border-border px-4 py-4 md:sticky md:top-0 md:h-screen md:w-56 md:shrink-0 md:overflow-y-auto md:border-b-0 md:border-r">
            <Link href="/dashboard" className="mb-4 block text-lg font-bold">
              NameCraft AI
            </Link>
            <Nav />
          </aside>
          <main className="min-w-0 flex-1 px-4 py-6 md:px-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
