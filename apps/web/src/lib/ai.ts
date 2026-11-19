"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export type AIOption = { value: string; label: string };

const NAMES: Record<string, string> = { ollama: "Ollama (내 PC)", claude_code: "Claude Code", antigravity: "Antigravity" };

/** 지금 실제로 쓸 수 있는 AI 만 고를 수 있게 한다(켜져 있고 실행 가능한 것). */
export function useAIOptions() {
  const [opts, setOpts] = useState<AIOption[]>([{ value: "none", label: "AI 없이 (빠름)" }]);
  const [hasOff, setHasOff] = useState(false);
  useEffect(() => {
    apiFetch<{ provider_id: string; enabled?: boolean; execution_mode: string }[]>("ai/providers").then((r) => {
      if (!r.ok) return;
      const usable = r.data.filter((p) => p.enabled && ["native_local", "supported_cli_task"].includes(p.execution_mode));
      setOpts([{ value: "none", label: "AI 없이 (빠름)" }, ...usable.map((p) => ({ value: p.provider_id, label: NAMES[p.provider_id] }))]);
      setHasOff(usable.length < r.data.length);
    });
  }, []);
  return { opts, hasOff };
}
