import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import {
  levelBySlugQueryOptions,
  subjectBySlugQueryOptions,
  chaptersBySubjectQueryOptions,
  groupChaptersByTrimester,
} from "@/lib/queries/curriculum";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/_authenticated/library/$cycle/$levelSlug/$subjectSlug")({
  component: ChaptersByTrimester,
});

const TRIMESTER_LABEL: Record<number, string> = {
  0: "Non classé",
  1: "1er trimestre",
  2: "2e trimestre",
  3: "3e trimestre",
};

function ChaptersByTrimester() {
  const { cycle, levelSlug, subjectSlug } = Route.useParams();
  const { lang } = useI18n();
  const { data: level, isLoading: levelLoading } = useQuery(levelBySlugQueryOptions(levelSlug));
  const { data: subject, isLoading: subjectLoading } = useQuery(subjectBySlugQueryOptions(level?.id, subjectSlug));
  const { data: chapters, isLoading: chaptersLoading } = useQuery(chaptersBySubjectQueryOptions(subject?.id));

  const grouped = chapters ? groupChaptersByTrimester(chapters) : null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <BreadcrumbNav
        items={[
          { label: "Programme officiel", to: "/library" },
          { label: cycle, to: "/library/$cycle", params: { cycle } },
          {
            label: level ? (lang === "ar" ? level.label_ar : level.label_fr) : "…",
            to: "/library/$cycle/$levelSlug",
            params: { cycle, levelSlug },
          },
          { label: subject ? (lang === "ar" ? subject.name_ar : subject.name_fr) : "…" },
        ]}
      />
      {levelLoading || subjectLoading ? (
        <Skeleton className="mt-2 h-9 w-64" />
      ) : subject ? (
        <h1 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">
          {lang === "ar" ? subject.name_ar : subject.name_fr}
        </h1>
      ) : (
        <p className="mt-10 text-sm text-muted-foreground">Matière introuvable.</p>
      )}

      {chaptersLoading ? (
        <div className="mt-8 space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : grouped && grouped.size > 0 ? (
        <div className="mt-8 space-y-8">
          {[...grouped.entries()].map(([trimester, chaptersInTrimester]) => (
            <section key={trimester}>
              <div className="flex items-center gap-2">
                <h2 className="font-display text-sm font-semibold text-muted-foreground">
                  {TRIMESTER_LABEL[trimester]}
                </h2>
                <Badge variant="secondary">{chaptersInTrimester.length}</Badge>
              </div>
              <StaggerGroup className="mt-3 grid gap-3">
                {chaptersInTrimester.map((chapter) => (
                  <StaggerItem key={chapter.id}>
                    <Link
                      to="/library/$cycle/$levelSlug/$subjectSlug/$chapterId"
                      params={{ cycle, levelSlug, subjectSlug, chapterId: chapter.id }}
                    >
                      <Card className="hover-lift flex items-center justify-between gap-3 p-4">
                        <div>
                          <h3 className="text-sm font-semibold">
                            {lang === "ar" ? chapter.title_ar : chapter.title_fr}
                          </h3>
                          {(lang === "ar" ? chapter.summary_ar : chapter.summary_fr) && (
                            <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                              {lang === "ar" ? chapter.summary_ar : chapter.summary_fr}
                            </p>
                          )}
                        </div>
                      </Card>
                    </Link>
                  </StaggerItem>
                ))}
              </StaggerGroup>
            </section>
          ))}
        </div>
      ) : (
        subject && <p className="mt-10 text-sm text-muted-foreground">Aucun chapitre publié pour cette matière pour le moment.</p>
      )}
    </div>
  );
}
