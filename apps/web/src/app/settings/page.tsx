import Link from "next/link";
import { BarChart3, Database, FileText, History, LineChart, Upload, Bell } from "lucide-react";
import { AISettings } from "@/components/ai-settings";
import { Card } from "@/components/ui/card";

const MORE = [
  { href: "/reports", icon: FileText, title: "보고서 · 백업", desc: "PDF 보고서, CSV·JSON 내보내기, 복원, 데이터 삭제" },
  { href: "/imports", icon: Upload, title: "작명소 자료 비교", desc: "받은 감정서를 올려 계산과 맞는지 확인" },
  { href: "/ai/usage", icon: BarChart3, title: "AI 사용량", desc: "AI 별 사용 기록과 구독 한도" },
  { href: "/ai/sessions", icon: History, title: "AI 실행 기록", desc: "AI 요청 하나하나의 결과" },
  { href: "/ai/analytics", icon: LineChart, title: "AI 사용 추세", desc: "기간별 그래프" },
  { href: "/ai/settings", icon: Bell, title: "AI 알림 · 보존", desc: "한도 알림 기준, 기록 보존 기간" },
  { href: "/admin/data", icon: Database, title: "데이터 관리", desc: "한자·성씨 자료의 출처와 버전" },
];

export default function Page() {
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">설정</h1>
          <p className="mt-1 text-muted-foreground">AI 를 켜면 이름 후보를 더 다양하게 받을 수 있어요. 꺼도 모든 기능을 쓸 수 있어요.</p>
        </div>
        <AISettings />
      </section>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">더 많은 기능</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {MORE.map(({ href, icon: Icon, title, desc }) => (
            <Link key={href} href={href} className="group block">
              <Card className="flex h-full gap-3 p-4 transition group-hover:shadow-md">
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <div><p className="font-medium">{title}</p><p className="text-sm text-muted-foreground">{desc}</p></div>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
