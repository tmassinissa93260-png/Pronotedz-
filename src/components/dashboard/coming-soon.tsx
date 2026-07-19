import type { LucideIcon } from "lucide-react";
import { FadeIn } from "@/components/motion/fade-in";

export function ComingSoon({
  icon: Icon,
  title,
  body,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
}) {
  return (
    <div className="flex min-h-[70vh] items-center justify-center px-6">
      <FadeIn className="max-w-md text-center">
        <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-primary/10 text-primary">
          <Icon className="size-6" />
        </div>
        <h1 className="mt-5 font-display text-xl font-semibold">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{body}</p>
        <span className="mt-4 inline-flex items-center rounded-full bg-accent/12 px-3 py-1 text-xs font-semibold text-accent">
          Bientôt disponible
        </span>
      </FadeIn>
    </div>
  );
}
