import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ServiceWorkerRegister } from "@/components/sw-register";
import { TopNav } from "@/components/top-nav";

export const metadata: Metadata = {
  title: "NameCraft AI",
  description: "곧 태어날 아기 이름을 찾고 가족과 함께 고르는 개인용 작명 도구",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#24634c" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen overflow-x-hidden antialiased">
        <ServiceWorkerRegister />
        <TopNav />
        <main className="mx-auto min-w-0 max-w-6xl px-4 py-6 sm:py-8">{children}</main>
      </body>
    </html>
  );
}
