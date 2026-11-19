import { NameAnalyzer } from "@/components/naming/name-analyzer";

export default function Page() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">이름 분석</h1>
        <p className="mt-1 text-sm text-muted-foreground">이름을 직접 입력해 분석하거나, 한글 이름에 맞는 한자 조합을 찾습니다.</p>
      </header>
      <NameAnalyzer />
    </div>
  );
}
