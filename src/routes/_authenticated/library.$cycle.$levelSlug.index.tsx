import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { BookText } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { levelBySlugQueryOptions, subjectsByLevelQueryOptions } from "@/lib/queries/curriculum";
import { CYCLES } from "@/lib/curriculum/school-levels";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/_authenticated/library/$cycle/$levelSlug/")({
  component: SubjectPicker,
});

function SubjectPicker() {
  const { cycle, levelSlug } = Route.useParams();
  const { lang } = useI18n();
  const cycleMeta = CYCLES.find((c) => c.value === cycle);
  const { data: level, isLoading: levelLoading } = useQuery(levelBySlugQueryOptions(levelSlug));
  const { data: subjects, isLoading: subjectsLoading } = useQuery(subjectsByLevelQueryOptions(level?.id));

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <BreadcrumbNav
        items={[
          { label: "Programme officiel", to: "/library" },
          {
            label: cycleMeta ? (lang === "ar" ? cycleMeta.label_ar : cycleMeta.label_fr) : cycle,
            to: "/library/$cycle",
            params: { cycle },
          },
          { label: level ? (lang === "ar" ? level.label_ar : level.label_fr) : "…" },
        ]}
      />
      {levelLoading ? (
        <Skeleton className="mt-2 h-9 w-64" />
      ) : level ? (
        <h1 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">
          {lang === "ar" ? level.label_ar : level.label_fr}
        </h1>
      ) : (
        <p className="mt-10 text-sm text-muted-foreground">Niveau introuvable.</p>
      )}

      {subjectsLoading ? (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : subjects && subjects.length > 0 ? (
        <StaggerGroup className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {subjects.map((subject) => (
            <StaggerItem key={subject.id}>
              <Link
                to="/library/$cycle/$levelSlug/$subjectSlug"
                params={{ cycle, levelSlug, subjectSlug: subject.slug }}
              >
                <Card className="hover-lift flex h-full items-center gap-3 p-5">
                  <div
                    className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/12 text-primary"
                    style={subject.color ? { backgroundColor: `${subject.color}22`, color: subject.color } : undefined}
                  >
                    <BookText className="size-5" />
                  </div>
                  <h2 className="font-display text-sm font-semibold">
                    {lang === "ar" ? subject.name_ar : subject.name_fr}
                  </h2>
                </Card>
              </Link>
            </StaggerItem>
          ))}
        </StaggerGroup>
      ) : (
        level && <p className="mt-10 text-sm text-muted-foreground">Aucune matière publiée pour ce niveau pour le moment.</p>
      )}
    </div>
  );
}
