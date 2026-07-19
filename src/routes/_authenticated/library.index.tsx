import { createFileRoute, Link } from "@tanstack/react-router";
import { GraduationCap, School, Landmark, Building2, Sparkle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { CYCLES } from "@/lib/curriculum/school-levels";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/_authenticated/library/")({
  component: LibraryCyclePicker,
});

const ICONS = { primaire: School, cem: GraduationCap, lycee: Landmark, universite: Building2, autre: Sparkle };

function LibraryCyclePicker() {
  const { lang } = useI18n();
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Programme officiel</h1>
      <p className="mt-1 text-muted-foreground">
        Le programme algérien complet — choisis ton cycle pour commencer.
      </p>

      <StaggerGroup className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CYCLES.filter((c) => c.value !== "autre").map((cycle) => {
          const Icon = ICONS[cycle.value];
          return (
            <StaggerItem key={cycle.value}>
              <Link to="/library/$cycle" params={{ cycle: cycle.value }}>
                <Card className="hover-lift h-full p-6">
                  <div className="grid size-12 place-items-center rounded-2xl bg-primary/12 text-primary">
                    <Icon className="size-6" />
                  </div>
                  <h2 className="mt-4 font-display text-lg font-semibold">
                    {lang === "ar" ? cycle.label_ar : cycle.label_fr}
                  </h2>
                </Card>
              </Link>
            </StaggerItem>
          );
        })}
      </StaggerGroup>
    </div>
  );
}
