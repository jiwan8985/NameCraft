"use client";

import { useEffect, useState } from "react";
import { BookOpen, Sparkles } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

export type NamingMethod = "none" | "ollama";

export const AI_NAME: Record<NamingMethod, string> = { ollama: "Ollama", none: "이름 사전" };

export function useLocalAI() {
  const [available, setAvailable] = useState<boolean | null>(null);
  useEffect(() => {
    let active = true;
    apiFetch<{ models: { can_generate: boolean; is_remote?: boolean }[] }>("ai/providers/ollama").then((result) => {
      if (active) setAvailable(result.ok && !!result.data.models?.some((model) => model.can_generate && !model.is_remote));
    });
    return () => { active = false; };
  }, []);
  return available;
}

export function AIPicker({ value, onChange, localAvailable }: {
  value: NamingMethod; onChange: (method: NamingMethod) => void; localAvailable: boolean | null;
}) {
  const methods: NamingMethod[] = localAvailable || value === "ollama"
    ? ["ollama", "none"]
    : ["none"];
  return (
    <div role="radiogroup" aria-label="이름 추천 방식" className="grid gap-2 sm:grid-cols-2">
      {methods.map((method) => {
        const Icon = method === "none" ? BookOpen : Sparkles;
        return (
          <button key={method} type="button" role="radio" aria-checked={value === method}
                  onClick={() => onChange(method)}
                  className={cn("flex items-center gap-2 rounded-xl border p-3 text-left text-sm font-semibold",
                                value === method ? "border-primary bg-primary-soft text-primary" : "border-border bg-card hover:bg-muted")}>
            <Icon className="size-4 shrink-0" aria-hidden="true" />{AI_NAME[method]}
          </button>
        );
      })}
    </div>
  );
}
