import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Sparkles, Wand2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { Reveal } from "@/components/library/reveal";
import { FadeIn } from "@/components/motion/fade-in";
import {
  lessonByIdQueryOptions,
  type LessonContent,
  type LessonExercise,
  type LessonSujet,
} from "@/lib/queries/curriculum";
import { useGenerateLessonContent } from "@/hooks/use-curriculum-ai";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute(
  "/_authenticated/library/$cycle/$levelSlug/$subjectSlug/$chapterId/$lessonId",
)({
  component: LessonDetail,
});

function LessonDetail() {
  const { cycle, levelSlug, subjectSlug, chapterId, lessonId } = Route.useParams();
  const { lang } = useI18n();
  const { data: lesson, isLoading } = useQuery(lessonByIdQueryOptions(lessonId));
  const generate = useGenerateLessonContent(lessonId);

  async function handleGenerate(simplify = false) {
    try {
      await generate.mutateAsync({ simplify });
      toast.success(simplify ? "Nouvelle explication prête." : "Leçon générée.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de générer la leçon pour le moment.");
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <Skeleton className="h-9 w-72" />
        <Skeleton className="mt-6 h-64 w-full" />
      </div>
    );
  }

  if (!lesson) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 text-center sm:px-6">
        <p className="text-sm text-muted-foreground">Leçon introuvable.</p>
      </div>
    );
  }

  const content = lesson.lesson_content as LessonContent | null;
  const exercises = (lesson.exercises as LessonExercise[] | null) ?? [];
  const sujet = lesson.sujet as LessonSujet | null;

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
          {
            label: "Chapitre",
            to: "/library/$cycle/$levelSlug/$subjectSlug/$chapterId",
            params: { cycle, levelSlug, subjectSlug, chapterId },
          },
          { label: lang === "ar" ? lesson.title_ar : lesson.title_fr },
        ]}
      />
      <h1 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">
        {lang === "ar" ? lesson.title_ar : lesson.title_fr}
      </h1>

      {!content ? (
        <Card className="mt-8 flex flex-col items-center gap-4 p-8 text-center">
          <div className="grid size-12 place-items-center rounded-2xl bg-primary/12 text-primary">
            <Sparkles className="size-6" />
          </div>
          <div>
            <h3 className="font-display text-base font-semibold">Cette leçon n'a pas encore été générée</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              L'IA va expliquer cette leçon, puis proposer des exercices corrigés et un sujet type examen.
            </p>
          </div>
          <Button onClick={() => handleGenerate(false)} disabled={generate.isPending}>
            {generate.isPending ? "Génération…" : "Générer avec l'IA"}
          </Button>
        </Card>
      ) : (
        <FadeIn className="mt-8">
          <Tabs defaultValue="lecon">
            <TabsList>
              <TabsTrigger value="lecon">Leçon</TabsTrigger>
              <TabsTrigger value="exercices">
                Exercices {exercises.length > 0 && <Badge className="ml-1.5">{exercises.length}</Badge>}
              </TabsTrigger>
              <TabsTrigger value="sujet">Sujet</TabsTrigger>
            </TabsList>

            <TabsContent value="lecon" className="space-y-4">
              <Card className="p-5">
                <div className="whitespace-pre-wrap text-sm leading-relaxed">
                  {content.simplified ?? content.explanation}
                </div>
              </Card>
              {content.key_points && content.key_points.length > 0 && (
                <Card className="p-5">
                  <h3 className="font-display text-sm font-semibold">À retenir</h3>
                  <ul className="mt-3 space-y-2">
                    {content.key_points.map((point, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                        <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
                        {point}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleGenerate(true)}
                disabled={generate.isPending}
              >
                <Wand2 className="size-4" />
                {generate.isPending ? "…" : "Réexplique-moi plus simplement"}
              </Button>
            </TabsContent>

            <TabsContent value="exercices" className="space-y-3">
              {exercises.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucun exercice pour cette leçon.</p>
              ) : (
                exercises.map((ex, i) => (
                  <Card key={i} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-medium">
                        {i + 1}. {ex.question}
                      </p>
                      {ex.difficulty && <Badge variant="outline" className="shrink-0">{ex.difficulty}</Badge>}
                    </div>
                    <Reveal label="Voir la correction" className="mt-3">
                      {ex.correction}
                    </Reveal>
                  </Card>
                ))
              )}
            </TabsContent>

            <TabsContent value="sujet">
              {!sujet ? (
                <p className="text-sm text-muted-foreground">Aucun sujet pour cette leçon.</p>
              ) : (
                <Card className="p-5">
                  <h3 className="font-display text-sm font-semibold">Sujet type examen</h3>
                  <p className="mt-3 whitespace-pre-wrap text-sm text-muted-foreground">{sujet.statement}</p>
                  <Reveal label="Voir la correction" className="mt-4">
                    <span className="whitespace-pre-wrap">{sujet.correction}</span>
                  </Reveal>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </FadeIn>
      )}
    </div>
  );
}
