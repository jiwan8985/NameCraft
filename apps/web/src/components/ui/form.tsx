import * as React from "react";
import { cn } from "@/lib/utils";

const field = "w-full rounded-md border border-border bg-card px-3 py-2 text-sm placeholder:text-muted-foreground";

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
      <label htmlFor={htmlFor} className="block text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function Notice({ tone = "info", children, role }: { tone?: "info" | "warn" | "danger"; children: React.ReactNode; role?: string }) {
  const tones = { info: "border-info text-info", warn: "border-warn text-warn", danger: "border-danger text-danger" };
  return (
    <p role={role} className={cn("rounded-md border px-3 py-2 text-sm", tones[tone])}>
      {children}
    </p>
  );
}

/** 쉼표·공백으로 구분한 한글 목록 */
export function splitList(s: string): string[] {
  return s.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean);
}
