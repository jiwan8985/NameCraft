"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { RadarChart } from "@/components/score";
import { Card, CardTitle } from "@/components/ui/card";
import { Notice } from "@/components/ui/form";
import { apiFetch } from "@/lib/api";
import { CATEGORY_ORDER, CATEGORY_SHORT, type RankedItem } from "@/lib/types";

/** /compare — 같은 기준으로 2~10개 후보 비교: 레이더 차트 + 표(대체 뷰) */
export function CompareView() {
  const sp = useSearchParams();
  const project = sp.get("project");
  const ids = (sp.get("ids") ?? "").split(",").filter(Boolean);
  const [items, setItems] = useState<RankedItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!project || ids.length < 2) return;
    apiFetch<{ items: RankedItem[] }>(`projects/${project}/candidates?include_excluded=true`).then((r) => {
      if (!r.ok) return setError(r.error.message);
      setItems(r.data.items.filter((i) => ids.includes(i.id!)));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, sp.get("ids")]);

  if (!project || ids.length < 2) return <Notice>추천 화면에서 후보를 2개 이상 선택하면 비교할 수 있습니다.</Notice>;
  if (error) return <Notice tone="danger" role="alert">{error}</Notice>;
  if (!items) return <p aria-busy="true" className="text-sm text-muted-foreground">불러오는 중…</p>;
  return (
    <div className="space-y-4">
      <Card><RadarChart series={items.map((i) => ({ name: i.full_hangul, categories: i.categories }))} /></Card>
      <Card className="overflow-x-auto">
        <CardTitle>비교표</CardTitle>
        <table className="mt-2 w-full min-w-[640px] text-sm">
          <thead className="text-left text-xs text-muted-foreground">
            <tr><th className="py-1">이름</th><th>한자</th><th>종합</th>{CATEGORY_ORDER.map((k) => <th key={k}>{CATEGORY_SHORT[k]}</th>)}<th>공식 한자</th><th>검토</th></tr>
          </thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.id} className="border-t border-border">
                <th scope="row" className="py-1 text-left">{i.full_hangul}</th>
                <td>{i.given_hanja ?? "—"}</td>
                <td className="tabular-nums font-semibold">{i.overall ?? "N/A"}</td>
                {CATEGORY_ORDER.map((k) => <td key={k} className="tabular-nums">{i.categories[k].score ?? "N/A"}</td>)}
                <td className="text-xs">{i.given_hanja ? i.gate.official_hanja : "한글 이름"}</td>
                <td className="text-xs">{i.gate.caution === "review" ? "검토 권장" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-muted-foreground">N/A 는 근거 자료가 없어 계산하지 않은 항목입니다(0점 아님). 전통 해석 항목은 같은 학파 프로필 안에서의 상대 비교입니다.</p>
      </Card>
    </div>
  );
}
