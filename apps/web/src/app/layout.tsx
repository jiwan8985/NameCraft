import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ServiceWorkerRegister } from "@/components/sw-register";
import { TopNav } from "@/components/top-nav";

export const metadata: Metadata = {
  title: "NameCraft AI",
  description: "검증 가능한 개인용 AI 작명 플랫폼",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#6d6ee0" };

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
