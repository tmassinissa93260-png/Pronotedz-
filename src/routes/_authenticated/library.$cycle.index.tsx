import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { levelsByCycleQueryOptions } from "@/lib/queries/curriculum";
import { CYCLES, type Cycle } from "@/lib/curriculum/school-levels";
import { useI18n } from "@/lib/i18n";

const VALID_CYCLES = new Set(CYCLES.map((c) => c.value));

export const Route = createFileRoute("/_authenticated/library/$cycle/")({
  beforeLoad: ({ params }) => {
    if (!VALID_CYCLES.has(params.cycle as Cycle)) throw notFound();
  },
  component: LevelPicker,
});

function LevelPicker() {
  const { cycle } = Route.useParams();
  const { lang } = useI18n();
  const cycleMeta = CYCLES.find((c) => c.value === cycle)!;
  const { data: levels, isLoading } = useQuery(levelsByCycleQueryOptions(cycle as Cycle));

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <BreadcrumbNav items={[{ label: "Programme officiel", to: "/library" }, { label: lang === "ar" ? cycleMeta.label_ar : cycleMeta.label_fr }]} />
      <h1 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">
        {lang === "ar" ? cycleMeta.label_ar : cycleMeta.label_fr}
      </h1>

      {isLoading ? (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : levels && levels.length > 0 ? (
        <StaggerGroup className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {levels.map((level) => (
            <StaggerItem key={level.id}>
              <Link to="/library/$cycle/$levelSlug" params={{ cycle, levelSlug: level.slug }}>
                <Card className="hover-lift h-full p-5">
                  <h2 className="font-display text-base font-semibold">
                    {lang === "ar" ? level.label_ar : level.label_fr}
                  </h2>
                  {level.track && <p className="mt-1 text-xs text-muted-foreground">{level.track}</p>}
                </Card>
              </Link>
            </StaggerItem>
          ))}
        </StaggerGroup>
      ) : (
        <p className="mt-10 text-sm text-muted-foreground">
          Aucun niveau publié pour ce cycle pour le moment.
        </p>
      )}
    </div>
  );
}
