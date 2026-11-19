import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 rounded-full text-sm font-medium transition active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-sm hover:brightness-105",
        soft: "bg-primary-soft text-primary hover:brightness-95",
        outline: "border border-border bg-card hover:bg-muted",
        ghost: "hover:bg-muted text-muted-foreground hover:text-foreground",
      },
      size: { default: "h-10 px-5", sm: "h-8 px-3.5 text-xs", lg: "h-12 px-7 text-base", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export function Button({
  className,
  variant,
  size,
  ...props
}: React.ComponentProps<"button"> & VariantProps<typeof buttonVariants>) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { buttonVariants };
