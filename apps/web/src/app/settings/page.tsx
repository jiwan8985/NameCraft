import { AISettings } from "@/components/ai-settings";

export default function Page() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">설정</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          AI 사용 여부를 정합니다. 학파·가중치는 프로젝트별 분석 옵션으로 저장됩니다. 유료 API 키는 입력받지 않습니다.
        </p>
      </header>
      <AISettings />
    </div>
  );
}
