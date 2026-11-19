import { cn } from "@/lib/utils";

/**
 * 검증 상태·데이터 출처 배지 (기획서 §22.3, §30.4).
 * 색상만으로 의미를 전달하지 않도록 항상 텍스트 라벨과 기호를 함께 표시한다.
 */
const STATUS: Record<string, { label: string; symbol: string; tone: string }> = {
  verified: { label: "공식 확인", symbol: "✓", tone: "text-ok border-ok" },
  calculated: { label: "계산값", symbol: "=", tone: "text-info border-info" },
  traditional_interpretation: { label: "전통 해석", symbol: "◇", tone: "text-foreground border-border" },
  subjective: { label: "주관·AI", symbol: "~", tone: "text-muted-foreground border-border" },
  unverified: { label: "미확인", symbol: "?", tone: "text-warn border-warn" },
  not_applicable: { label: "해당 없음", symbol: "–", tone: "text-muted-foreground border-border" },
  conflict: { label: "자료 충돌", symbol: "!", tone: "text-danger border-danger" },
  official: { label: "공식", symbol: "✓", tone: "text-ok border-ok" },
  local_observed: { label: "로컬 관측", symbol: "◉", tone: "text-info border-info" },
  manual: { label: "수동 입력", symbol: "✎", tone: "text-foreground border-border" },
  estimated: { label: "추정", symbol: "≈", tone: "text-warn border-warn" },
  unknown: { label: "확인 불가", symbol: "?", tone: "text-muted-foreground border-border" },
  not_supported: { label: "미지원", symbol: "×", tone: "text-muted-foreground border-border" },
  stale: { label: "오래됨", symbol: "⧗", tone: "text-warn border-warn" },
  demo: { label: "DEMO DATA", symbol: "◆", tone: "text-mock border-mock" },
  mock: { label: "MOCK", symbol: "◆", tone: "text-mock border-mock" },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const s = STATUS[status] ?? { label: status, symbol: "·", tone: "text-muted-foreground border-border" };
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium", s.tone, className)}
      data-status={status}
    >
      <span aria-hidden="true">{s.symbol}</span>
      {s.label}
    </span>
  );
}
