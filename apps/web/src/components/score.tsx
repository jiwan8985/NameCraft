import { CATEGORY_ORDER, CATEGORY_SHORT, type Category } from "@/lib/types";

/** 점수 막대 — 값이 없으면 N/A 로 표시하고 0으로 그리지 않는다. */
export function ScoreBar({ label, value, hint }: { label: string; value: number | null; hint?: string }) {
  return (
    <div className="grid grid-cols-[4.5rem_1fr_2.5rem] items-center gap-2 text-xs" title={hint}>
      <span className="text-muted-foreground">{label}</span>
      {value === null ? (
        <span className="h-2 rounded-full border border-dashed border-border" aria-hidden="true" />
      ) : (
        <span className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden="true">
          <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
        </span>
      )}
      <span className="text-right tabular-nums">{value === null ? "N/A" : Math.round(value)}</span>
    </div>
  );
}

export function CategoryBars({ categories }: { categories: Record<string, Category> }) {
  return (
    <div className="space-y-1">
      {CATEGORY_ORDER.map((k) => (
        <ScoreBar key={k} label={CATEGORY_SHORT[k]} value={categories[k]?.score ?? null} hint={categories[k]?.basis} />
      ))}
    </div>
  );
}

const COLORS = ["var(--primary)", "var(--info)", "var(--warn)", "var(--mock)", "var(--ok)", "var(--danger)"];

/** 레이더 차트 (SVG). N/A 축은 0이 아니라 '값 없음' 점선으로 표시. 표 대체 뷰를 함께 제공한다. */
export function RadarChart({ series, size = 260 }: { series: { name: string; categories: Record<string, Category> }[]; size?: number }) {
  const axes = CATEGORY_ORDER;
  const c = size / 2;
  const r = c - 34;
  const point = (i: number, v: number) => {
    const a = (Math.PI * 2 * i) / axes.length - Math.PI / 2;
    return [c + Math.cos(a) * r * (v / 100), c + Math.sin(a) * r * (v / 100)];
  };
  return (
    <figure className="space-y-2">
      <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto w-full max-w-xs" role="img" aria-label="후보 비교 레이더 차트">
        {[25, 50, 75, 100].map((lv) => (
          <polygon key={lv} points={axes.map((_, i) => point(i, lv).join(",")).join(" ")} fill="none" stroke="var(--border)" />
        ))}
        {axes.map((k, i) => {
          const [x, y] = point(i, 118);
          return (
            <text key={k} x={x} y={y} fontSize="11" textAnchor="middle" dominantBaseline="middle" fill="var(--muted-foreground)">
              {CATEGORY_SHORT[k]}
            </text>
          );
        })}
        {series.map((s, si) => {
          const pts = axes.map((k, i) => point(i, s.categories[k]?.score ?? 0));
          const hasNA = axes.some((k) => s.categories[k]?.score === null);
          return (
            <polygon
              key={s.name}
              points={pts.map((p) => p.join(",")).join(" ")}
              fill={COLORS[si % COLORS.length]}
              fillOpacity={0.12}
              stroke={COLORS[si % COLORS.length]}
              strokeDasharray={hasNA ? "4 3" : undefined}
              strokeWidth={2}
            />
          );
        })}
      </svg>
      <figcaption className="flex flex-wrap justify-center gap-3 text-xs">
        {series.map((s, si) => (
          <span key={s.name} className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-3 rounded-sm" style={{ background: COLORS[si % COLORS.length] }} aria-hidden="true" />
            {s.name}
          </span>
        ))}
        <span className="text-muted-foreground">점선 = N/A 항목 포함(0점 아님)</span>
      </figcaption>
    </figure>
  );
}
