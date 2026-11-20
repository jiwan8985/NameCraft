import { useId, useState } from "react";

export type ChartPoint = { date: string; value: number | null };

const compact = new Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: 1 });
const full = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 });

export function LineChart({ points, unit, label, variant = "line" }: {
  points: ChartPoint[]; unit: string; label: string; variant?: "line" | "bars";
}) {
  const fill = useId();
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const height = 160;
  const width = 600;
  const slot = width / Math.max(points.length, 1);
  const barWidth = Math.min(45, slot * .62);
  const values = points.flatMap(({ value }) => value === null ? [] : [value]);
  const peak = Math.max(1, ...values);
  const interval = 10 ** Math.floor(Math.log10(peak));
  const max = Math.ceil(peak / interval) * interval;
  const x = (i: number) => (i + .5) * slot;
  const y = (value: number) => height - value / max * height;
  const activeIndex = points.findIndex(({ date }) => date === selectedDate);
  const currentIndex = activeIndex < 0 ? points.length - 1 : activeIndex;
  const current = points[currentIndex];
  const displayUnit = unit === "count" ? "건" : unit === "tokens" ? "토큰" : unit;
  const segments: [number, number][][] = [];
  let segment: [number, number][] = [];
  points.forEach((point, i) => {
    if (point.value === null) {
      if (segment.length) segments.push(segment);
      segment = [];
    } else segment.push([x(i), y(point.value)]);
  });
  if (segment.length) segments.push(segment);

  return (
    <figure className="usage-plot rounded-2xl px-4 py-5 sm:px-7 sm:py-6">
      <figcaption className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-emerald-50/75">{label}</p>
          <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums text-white">
            {current?.value == null ? "—" : full.format(current.value)}
            {current?.value != null && <span className="ml-1.5 text-sm font-normal text-emerald-50/75">{displayUnit}</span>}
          </p>
        </div>
        {current && <time dateTime={current.date} className="rounded-full border border-white/15 px-3 py-1 text-xs font-medium text-emerald-50/85">{current.date.replaceAll("-", ".")}</time>}
      </figcaption>
      {values.length ? (
        <div className="mt-5">
          <div className="grid grid-cols-[2.4rem_1fr]">
            <div className="flex h-36 flex-col justify-between pr-2 text-right text-[11px] tabular-nums text-emerald-50/65 sm:h-48">
              {[max, max / 2, 0].map((value) => <span key={value}>{compact.format(value)}</span>)}
            </div>
            <div className="relative h-36 min-w-0 sm:h-48">
              <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="absolute inset-0 size-full"
                   role="img" aria-label={`${label} 추이 (${unit})`}>
                <defs><linearGradient id={fill} x2="0" y2="1">
                  <stop offset="0%" stopColor="#b5f2d0" stopOpacity=".28" />
                  <stop offset="100%" stopColor="#b5f2d0" stopOpacity="0" />
                </linearGradient></defs>
                {[0, height / 2, height].map((v) => (
                  <line key={v} x1="0" x2={width} y1={v} y2={v} stroke="white" strokeOpacity=".16" strokeDasharray={v === height ? undefined : "4 5"} vectorEffect="non-scaling-stroke" />
                ))}
                {variant === "bars" ? points.map(({ value, date }, i) => {
                  if (value == null) return null;
                  const visible = Math.max(2, height - y(value));
                  return <rect key={date} x={x(i) - barWidth / 2} y={height - visible} width={barWidth} height={visible}
                               rx={Math.min(5, barWidth / 3, visible / 2)} fill={currentIndex === i ? "#e6ffb5" : "#82cba8"} opacity={currentIndex === i ? 1 : .78} />;
                }) : (
                  <>
                    {segments.map((part, i) => {
                      const path = part.map((xy) => xy.join(",")).join(" ");
                      return (
                        <g key={i}>
                          {part.length > 1 && <polygon points={`${part[0][0]},${height} ${path} ${part.at(-1)![0]},${height}`} fill={`url(#${fill})`} />}
                          <polyline points={path} fill="none" stroke="#b5f2d0" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
                        </g>
                      );
                    })}
                    {points.map(({ value, date }, i) => value !== null && (
                      <circle key={date} cx={x(i)} cy={y(value)} r={i === currentIndex ? 4 : 2} fill={i === currentIndex ? "#e6ffb5" : "#b5f2d0"} />
                    ))}
                  </>
                )}
              </svg>
              <div className="absolute inset-0 grid" style={{ gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))` }}>
                {points.map(({ date, value }, i) => (
                  <button key={date} type="button" className="min-w-0 rounded-sm hover:bg-white/8 focus-visible:bg-white/12 focus-visible:outline-white"
                          title={`${date} · ${value == null ? "미보고" : full.format(value) + " " + displayUnit}`}
                          aria-label={`${date} ${value == null ? "미보고" : full.format(value) + " " + displayUnit}`}
                          aria-pressed={i === currentIndex} tabIndex={i === currentIndex ? 0 : -1}
                          onMouseEnter={() => setSelectedDate(date)} onClick={() => setSelectedDate(date)}
                          onFocus={() => setSelectedDate(date)}
                          onKeyDown={(event) => {
                            const adjacent = event.key === "ArrowLeft" ? event.currentTarget.previousElementSibling
                              : event.key === "ArrowRight" ? event.currentTarget.nextElementSibling : null;
                            if (adjacent instanceof HTMLElement) { event.preventDefault(); adjacent.focus(); }
                          }} />
                ))}
              </div>
            </div>
          </div>
          <div className="ml-10 mt-2 flex justify-between text-[11px] text-emerald-50/65">
            <span>{points[0].date.slice(5).replace("-", "/")}</span>
            {points.length > 1 && <span>{points.at(-1)!.date.slice(5).replace("-", "/")}</span>}
          </div>
        </div>
      ) : <p className="mt-5 border-t border-white/15 pt-4 text-sm text-emerald-50/75">이 기간에 기록된 값이 없어요.</p>}
    </figure>
  );
}

export function Heatmap({ grid, rows }: { grid: number[][]; rows: string[] }) {
  const max = Math.max(0, ...grid.flat());
  if (!max) return <p className="mt-3 rounded-xl bg-muted p-4 text-sm text-muted-foreground">선택한 기간에 기록된 요청이 없어요.</p>;
  const activeDay = grid.findIndex((row) => row.includes(max));
  const peakHour = grid[activeDay].indexOf(max);
  return (
    <figure className="mt-4 space-y-3">
      <div className="grid items-center gap-0.5 sm:gap-1" style={{ gridTemplateColumns: "1.4rem repeat(24, minmax(0, 1fr))" }} role="img" aria-label="요일·시간대별 요청 빈도">
        <span />
        {grid[0]?.map((_, h) => <span key={h} className="text-xs tabular-nums text-muted-foreground">{h % 6 === 0 ? h : ""}</span>)}
        {grid.map((row, d) => [
          <span key={`day-${d}`} className="text-xs text-muted-foreground">{rows[d]}</span>,
          ...row.map((value, h) => <span key={`${d}-${h}`} title={`${rows[d]} ${h}시 · ${value}건`} className="aspect-square rounded-[4px] ring-1 ring-inset ring-primary/10"
            style={{ background: value ? `color-mix(in oklch, var(--primary) ${25 + 75 * value / max}%, var(--muted))` : "var(--muted)" }} />),
        ])}
      </div>
      <figcaption className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-primary-soft/45 px-3 py-2 text-xs text-muted-foreground">
        <span>가장 많이 사용한 시간</span>
        <span className="font-semibold text-primary">{rows[activeDay]}요일 {peakHour}시 · {full.format(max)}건</span>
      </figcaption>
    </figure>
  );
}

export type ModelActivity = { model_id: string; requests: number };

export function ModelBars({ models }: { models: ModelActivity[] }) {
  const total = models.reduce((sum, model) => sum + model.requests, 0);
  if (!total) return <p className="mt-3 rounded-xl bg-muted p-4 text-sm text-muted-foreground">모델 사용 기록이 없어요.</p>;
  return (
    <ul className="mt-4 space-y-4">
      {models.map(({ model_id, requests }) => (
        <li key={model_id}>
          <div className="mb-1.5 flex items-start justify-between gap-3 text-sm">
            <span className="min-w-0 break-all font-medium">{model_id === "unknown" ? "모델 정보 없음" : model_id}</span>
            <span className="shrink-0 tabular-nums text-muted-foreground">{requests.toLocaleString("ko-KR")}건</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
            <div className="usage-model-bar h-full rounded-full" style={{ width: `${100 * requests / total}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
