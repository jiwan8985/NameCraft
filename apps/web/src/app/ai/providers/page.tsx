"use client";

import { useCallback, useEffect, useState } from "react";
import { Cpu, RefreshCw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Notice } from "@/components/ui/form";
import { apiFetch, postJson } from "@/lib/api";

type Model = {
  name: string;
  size_bytes: number;
  estimated_memory_bytes: number;
  fit: "gpu" | "ram" | "tight" | "unknown";
  coding: boolean;
};

type Assessment = {
  hardware: {
    logical_cpus: number | null;
    ram_total_bytes: number | null;
    ram_available_bytes: number | null;
    gpus: { name: string; total_bytes: number; available_bytes: number }[];
  };
  models: Model[];
  recommended: string | null;
  selected_model: string | null;
  message: string;
};

const fitLabel: Record<Model["fit"], string> = {
  gpu: "GPU 메모리 여유",
  ram: "시스템 RAM 사용 예상",
  tight: "현재 메모리 여유 부족",
  unknown: "메모리 확인 필요",
};

function memory(bytes: number | null) {
  return bytes === null ? "확인 불가" : `${(bytes / 1024 ** 3).toFixed(1)} GiB`;
}

export default function Page() {
  const [data, setData] = useState<Assessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    const result = await apiFetch<Assessment>("ai/providers/ollama/recommendation");
    if (result.ok) setData(result.data);
    else setError(result.error.message);
    setLoading(false);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function apply(model: string) {
    setSaving(model);
    setError("");
    setNotice("");
    const result = await postJson("ai/preferences", { provider_id: "ollama", model_id: model }, "PATCH");
    if (result.ok) {
      setData((current) => current && { ...current, selected_model: model });
      setNotice(`앞으로 이름을 지을 때 ${model} 모델을 사용해요.`);
    } else {
      setError(result.error.message);
    }
    setSaving(null);
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Ollama 작명 모델</h1>
          <p className="mt-1 text-sm text-muted-foreground">현재 PC 사양과 설치된 모델을 비교해요.</p>
        </div>
        <Button variant="outline" size="sm" disabled={loading || saving !== null} onClick={refresh}>
          <RefreshCw className="size-4" aria-hidden="true" /> 사양 다시 확인
        </Button>
      </header>

      {error && <Notice role="alert" tone="danger">{error}</Notice>}
      {notice && <Notice role="status">{notice}</Notice>}
      {loading && <p role="status" className="text-sm text-muted-foreground">PC 사양과 모델을 확인하고 있어요.</p>}
      {data && (
        <>
          <Card className="space-y-3">
            <CardTitle className="flex items-center gap-2"><Cpu className="size-5 text-primary" aria-hidden="true" /> 이 PC의 사양</CardTitle>
            <dl className="grid gap-3 text-sm sm:grid-cols-3">
              <div><dt className="text-muted-foreground">CPU</dt><dd>{data.hardware.logical_cpus ?? "확인 불가"} 논리 프로세서</dd></div>
              <div><dt className="text-muted-foreground">시스템 RAM</dt><dd>{memory(data.hardware.ram_available_bytes)} 사용 가능 / {memory(data.hardware.ram_total_bytes)}</dd></div>
              <div><dt className="text-muted-foreground">GPU</dt>
                <dd>{data.hardware.gpus.length ? (
                  <ul>{data.hardware.gpus.map((gpu, i) => (
                    <li key={i}>{gpu.name} · {memory(gpu.available_bytes)} 여유 / {memory(gpu.total_bytes)}</li>
                  ))}</ul>
                ) : "GPU 메모리 확인 불가"}</dd>
              </div>
            </dl>
          </Card>

          <section aria-label="설치된 작명 모델" className="space-y-3">
            <p className="text-sm leading-relaxed text-muted-foreground">추천은 설치된 모델의 크기, 현재 메모리 여유, 글쓰기 용도를 바탕으로 합니다. 실제 메모리 사용량과 응답 속도는 달라질 수 있어요.</p>
            {data.models.length === 0 && <Notice>{data.message}</Notice>}
            {data.models.length > 0 && !data.recommended && <Notice tone="warn">현재 메모리 정보로는 여유 있게 실행할 모델을 추천하기 어려워요.</Notice>}
            {data.models.map((model) => {
              const recommended = model.name === data.recommended;
              const selected = model.name === data.selected_model;
              return (
                <Card key={model.name} className={`flex flex-wrap items-center justify-between gap-4 ${recommended ? "border-primary/40 bg-primary-soft" : ""}`}>
                  <div className="min-w-0 space-y-1">
                    {recommended && <p className="flex items-center gap-1.5 text-xs font-semibold text-primary"><Sparkles className="size-4" aria-hidden="true" /> 메모리 기준 추천</p>}
                    <CardTitle className="break-all">{model.name}</CardTitle>
                    <CardDescription>{fitLabel[model.fit]} · 모델 {memory(model.size_bytes)} · 예상 {memory(model.estimated_memory_bytes)}</CardDescription>
                    {model.coding && <p className="text-xs text-muted-foreground">코드 작업에 특화된 모델이에요.</p>}
                  </div>
                  <Button disabled={selected || saving !== null || loading} variant={recommended ? "default" : "outline"}
                          onClick={() => { void apply(model.name); }}>
                    {selected ? "현재 사용 중" : saving === model.name ? "적용 중…" : "작명에 적용"}
                  </Button>
                </Card>
              );
            })}
          </section>
        </>
      )}
    </div>
  );
}
