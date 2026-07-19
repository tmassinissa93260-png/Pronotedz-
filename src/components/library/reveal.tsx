import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/** Native <details>/<summary> — no JS state needed, works with reduced-motion and screen readers. */
export function Reveal({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <details className={cn("group rounded-xl border border-border bg-secondary/30 open:bg-secondary/50", className)}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 text-sm font-medium">
        {label}
        <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-border/60 px-4 py-3 text-sm text-muted-foreground">{children}</div>
    </details>
  );
}
