/** 의존성 없는 SVG 차트 (D-034). null 은 선을 끊어 '값 없음'으로 그리고 0 으로 그리지 않는다. */
export function LineChart({ points, unit, label, height = 120 }: { points: { date: string; value: number | null }[]; unit: string; label: string; height?: number }) {
  const w = 320, h = height, pad = 24;
  const vals = points.map((p) => p.value).filter((v): v is number => v !== null);
  const max = Math.max(1, ...vals);
  const x = (i: number) => pad + (i * (w - pad * 2)) / Math.max(1, points.length - 1);
  const y = (v: number) => h - pad - (v / max) * (h - pad * 2);
  const segs: string[] = [];
  let cur: string[] = [];
  points.forEach((p, i) => {
    if (p.value === null) { if (cur.length) segs.push(cur.join(" ")); cur = []; }
    else cur.push(`${x(i)},${y(p.value)}`);
  });
  if (cur.length) segs.push(cur.join(" "));
  return (
    <figure>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label={`${label} 추이 (${unit})`}>
        <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="var(--border)" />
        <text x={pad} y={pad - 8} fontSize="10" fill="var(--muted-foreground)">최대 {max} {unit}</text>
        {segs.map((s, i) => <polyline key={i} points={s} fill="none" stroke="var(--primary)" strokeWidth={2} />)}
        {points.map((p, i) => p.value !== null && <circle key={i} cx={x(i)} cy={y(p.value)} r={2} fill="var(--primary)" />)}
        <text x={pad} y={h - 6} fontSize="10" fill="var(--muted-foreground)">{points[0]?.date.slice(5)}</text>
        <text x={w - pad} y={h - 6} fontSize="10" textAnchor="end" fill="var(--muted-foreground)">{points[points.length - 1]?.date.slice(5)}</text>
      </svg>
    </figure>
  );
}

export function Heatmap({ grid, rows }: { grid: number[][]; rows: string[] }) {
  const max = Math.max(1, ...grid.flat());
  return (
    <div className="overflow-x-auto">
      <table className="text-[10px]" aria-label="요일·시간대 요청 수">
        <thead><tr><th />{Array.from({ length: 24 }, (_, h) => <th key={h} className="w-4 font-normal text-muted-foreground">{h % 6 === 0 ? h : ""}</th>)}</tr></thead>
        <tbody>{grid.map((row, d) => (
          <tr key={d}><th scope="row" className="pr-1 font-normal">{rows[d]}</th>
            {row.map((v, h) => <td key={h} title={`${rows[d]} ${h}시: ${v}건`} className="h-4 w-4 border border-card"
                                   style={{ background: v ? `color-mix(in oklch, var(--primary) ${20 + (v / max) * 80}%, transparent)` : "var(--muted)" }}>
              <span className="sr-only">{v}</span></td>)}</tr>))}
        </tbody>
      </table>
    </div>
  );
}
