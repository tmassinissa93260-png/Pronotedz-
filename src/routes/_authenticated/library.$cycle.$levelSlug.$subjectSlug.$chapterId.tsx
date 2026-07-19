import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Sparkles, BookOpen, CheckCircle2, Trophy } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { chapterByIdQueryOptions, lessonsByChapterQueryOptions } from "@/lib/queries/curriculum";
import { useGenerateLessonPlan } from "@/hooks/use-curriculum-ai";
import { useMarkChapterComplete } from "@/hooks/use-gamification";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/_authenticated/library/$cycle/$levelSlug/$subjectSlug/$chapterId")({
  component: LessonList,
});

function LessonList() {
  const { cycle, levelSlug, subjectSlug, chapterId } = Route.useParams();
  const { user } = Route.useRouteContext();
  const { lang } = useI18n();
  const { data: chapter, isLoading: chapterLoading } = useQuery(chapterByIdQueryOptions(chapterId));
  const { data: lessons, isLoading: lessonsLoading } = useQuery(lessonsByChapterQueryOptions(chapterId));
  const generatePlan = useGenerateLessonPlan(chapterId);
  const markComplete = useMarkChapterComplete(user.id);

  async function handleGeneratePlan() {
    try {
      await generatePlan.mutateAsync();
      toast.success("Plan de leçons généré.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de générer le plan pour le moment.");
    }
  }

  async function handleMarkComplete() {
    try {
      const res = await markComplete.mutateAsync(chapterId);
      if (!res.alreadyDone) toast.success("Chapitre terminé ! +20 XP");
    } catch {
      toast.error("Impossible d'enregistrer ta progression.");
    }
  }

  const allLessonsReady = Boolean(lessons?.length) && lessons!.every((l) => l.lesson_content);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <BreadcrumbNav
        items={[
          { label: "Programme officiel", to: "/library" },
          { label: cycle, to: "/library/$cycle", params: { cycle } },
          { label: levelSlug, to: "/library/$cycle/$levelSlug", params: { cycle, levelSlug } },
          {
            label: subjectSlug,
            to: "/library/$cycle/$levelSlug/$subjectSlug",
            params: { cycle, levelSlug, subjectSlug },
          },
          { label: chapter ? (lang === "ar" ? chapter.title_ar : chapter.title_fr) : "…" },
        ]}
      />

      {chapterLoading ? (
        <Skeleton className="mt-2 h-9 w-72" />
      ) : chapter ? (
        <>
          <h1 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">
            {lang === "ar" ? chapter.title_ar : chapter.title_fr}
          </h1>
          {(lang === "ar" ? chapter.summary_ar : chapter.summary_fr) && (
            <p className="mt-2 text-muted-foreground">{lang === "ar" ? chapter.summary_ar : chapter.summary_fr}</p>
          )}
        </>
      ) : (
        <p className="mt-10 text-sm text-muted-foreground">Chapitre introuvable.</p>
      )}

      <div className="mt-8">
        {lessonsLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : lessons && lessons.length > 0 ? (
          <StaggerGroup className="space-y-3">
            {lessons.map((lesson, i) => {
              const ready = Boolean(lesson.lesson_content);
              return (
                <StaggerItem key={lesson.id}>
                  <Link
                    to="/library/$cycle/$levelSlug/$subjectSlug/$chapterId/$lessonId"
                    params={{ cycle, levelSlug, subjectSlug, chapterId, lessonId: lesson.id }}
                  >
                    <Card className="hover-lift flex items-center gap-3 p-4">
                      <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-secondary text-xs font-semibold text-muted-foreground">
                        {i + 1}
                      </span>
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold">{lang === "ar" ? lesson.title_ar : lesson.title_fr}</h3>
                      </div>
                      {ready ? (
                        <CheckCircle2 className="size-4 shrink-0 text-primary" />
                      ) : (
                        <BookOpen className="size-4 shrink-0 text-muted-foreground" />
                      )}
                    </Card>
                  </Link>
                </StaggerItem>
              );
            })}
          </StaggerGroup>
        ) : null}

        {allLessonsReady && (
          <Button
            variant={markComplete.data?.alreadyDone ? "secondary" : "default"}
            className="mt-4 w-full"
            onClick={handleMarkComplete}
            disabled={markComplete.isPending || markComplete.data?.alreadyDone}
          >
            <Trophy className="size-4" />
            {markComplete.data?.alreadyDone ? "Chapitre terminé" : "Marquer ce chapitre comme terminé"}
          </Button>
        )}

        {!lessonsLoading && lessons && lessons.length === 0 && chapter ? (
          <Card className="flex flex-col items-center gap-4 p-8 text-center">
            <div className="grid size-12 place-items-center rounded-2xl bg-primary/12 text-primary">
              <Sparkles className="size-6" />
            </div>
            <div>
              <h3 className="font-display text-base font-semibold">Aucune leçon pour ce chapitre pour le moment</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                L'IA peut découper ce chapitre en leçons, sur le programme officiel de {levelSlug}.
              </p>
            </div>
            <Button onClick={handleGeneratePlan} disabled={generatePlan.isPending}>
              {generatePlan.isPending ? "Génération…" : "Générer le plan de leçons"}
            </Button>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
