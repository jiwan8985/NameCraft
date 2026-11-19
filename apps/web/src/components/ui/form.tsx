import * as React from "react";
import { cn } from "@/lib/utils";

const field = "w-full rounded-xl border border-border bg-card px-3.5 py-2.5 text-sm placeholder:text-muted-foreground outline-none transition focus:border-primary focus:ring-4 focus:ring-primary-soft";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input className={cn(field, className)} {...props} />;
}

export function Select({ className, ...props }: React.ComponentProps<"select">) {
  return <select className={cn(field, "pr-8", className)} {...props} />;
}

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return <textarea className={cn(field, "min-h-20", className)} {...props} />;
}

export function Field({ label, hint, children, htmlFor }: { label: string; hint?: string; htmlFor?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-foreground/90">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function Notice({ tone = "info", children, role }: { tone?: "info" | "warn" | "danger"; children: React.ReactNode; role?: string }) {
  const tones = { info: "bg-primary-soft text-primary", warn: "bg-warn-soft text-warn", danger: "bg-danger-soft text-danger" };
  return (
    <p role={role} className={cn("rounded-xl px-4 py-2.5 text-sm", tones[tone])}>
      {children}
    </p>
  );
}

/** 쉼표·공백으로 구분한 한글 목록 */
export function splitList(s: string): string[] {
  return s.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean);
}

/** 선택형 칩(토글) */
export function Chip({ active, className, ...props }: React.ComponentProps<"button"> & { active?: boolean }) {
  return (
    <button type="button" aria-pressed={active}
            className={cn("rounded-full border px-3.5 py-1.5 text-sm transition",
                          active ? "border-primary bg-primary-soft text-primary" : "border-border bg-card hover:bg-muted", className)}
            {...props} />
  );
}

/** 접었다 펴는 '자세히' 영역 */
export function Details({ summary, children, className }: { summary: string; children: React.ReactNode; className?: string }) {
  return (
    <details className={cn("group rounded-xl", className)}>
      <summary className="cursor-pointer list-none text-sm text-muted-foreground hover:text-foreground">
        <span className="inline-block transition group-open:rotate-90">›</span> {summary}
      </summary>
      <div className="mt-3">{children}</div>
    </details>
  );
}
