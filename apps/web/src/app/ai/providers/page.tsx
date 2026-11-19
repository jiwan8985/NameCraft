import { ProviderList } from "@/components/provider-list";
import { routeByPath } from "@/lib/routes";

export default function Page() {
  const r = routeByPath("/ai/providers");
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">{r.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{r.summary}</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Claude Code·Antigravity는 보유한 구독 계정의 공식 실행 방식만 사용하며, 유료 API 키는 입력받지 않습니다.
        </p>
      </header>
      <ProviderList />
    </div>
  );
}
