import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Star, Lock, PlayCircle, CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { FadeIn } from "@/components/motion/fade-in";
import {
  courseQueryOptions,
  courseVideosQueryOptions,
  courseReviewsQueryOptions,
  myEnrollmentQueryOptions,
} from "@/lib/queries/courses";
import { useEnrollInCourse } from "@/hooks/use-course-actions";
import { useStartCheckout } from "@/hooks/use-payment-actions";

export const Route = createFileRoute("/_authenticated/courses/$courseId")({
  component: CourseDetail,
});

function CourseDetail() {
  const { courseId } = Route.useParams();
  const { user } = Route.useRouteContext();
  const { data: course, isLoading } = useQuery(courseQueryOptions(courseId));
  const { data: videos } = useQuery(courseVideosQueryOptions(courseId));
  const { data: reviews } = useQuery(courseReviewsQueryOptions(courseId));
  const { data: enrollment } = useQuery(myEnrollmentQueryOptions(courseId, user.id));
  const enroll = useEnrollInCourse(courseId, user.id);
  const checkout = useStartCheckout();
  const [activeVideo, setActiveVideo] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (!course) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6">
        <p className="text-sm text-muted-foreground">Cours introuvable.</p>
      </div>
    );
  }

  const isTeacher = course.teacher_id === user.id;
  const hasAccess = isTeacher || Boolean(enrollment);
  const shownUrl = activeVideo ?? (hasAccess ? undefined : course.trailer_video_url);

  const price = course.price;

  async function handleEnroll() {
    try {
      if (price > 0) {
        const { checkoutUrl } = await checkout.mutateAsync({ itemType: "course", itemId: courseId });
        window.location.href = checkoutUrl;
        return;
      }
      const res = await enroll.mutateAsync();
      if (!res.alreadyEnrolled) toast.success("Inscription confirmée !");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de s'inscrire pour le moment.");
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <BreadcrumbNav items={[{ label: "Cours de profs", to: "/courses" }, { label: course.title }]} />

      <FadeIn>
        <Card className="mt-2 overflow-hidden">
          <div className="aspect-video bg-black">
            {shownUrl ? (
              <video src={shownUrl} controls className="size-full" />
            ) : (
              <div className="grid size-full place-items-center text-muted-foreground">
                <Lock className="size-8" />
              </div>
            )}
          </div>
          <div className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <Badge variant="secondary">{course.subject}</Badge>
                <h1 className="mt-2 font-display text-xl font-bold">{course.title}</h1>
                <p className="mt-1 text-sm text-muted-foreground">{course.teacher?.full_name ?? "Professeur"}</p>
              </div>
              {!isTeacher && (
                <div className="text-right">
                  <div className="font-display text-xl font-bold text-primary">
                    {course.price > 0 ? `${Number(course.price).toLocaleString()} DZD` : "Gratuit"}
                  </div>
                  {hasAccess ? (
                    <Badge className="mt-1">
                      <CheckCircle2 className="size-3" /> Inscrit
                    </Badge>
                  ) : (
                    <Button className="mt-2" onClick={handleEnroll} disabled={enroll.isPending || checkout.isPending}>
                      {enroll.isPending || checkout.isPending ? "…" : course.price > 0 ? "Payer et s'inscrire" : "S'inscrire"}
                    </Button>
                  )}
                </div>
              )}
            </div>
            {course.description && <p className="mt-4 text-sm leading-relaxed text-muted-foreground">{course.description}</p>}
          </div>
        </Card>

        {videos && videos.length > 0 && (
          <Card className="mt-4 p-5">
            <h2 className="font-display text-sm font-semibold">Contenu du cours ({videos.length} vidéos)</h2>
            <div className="mt-3 space-y-2">
              {videos.map((v, i) => {
                const unlocked = v.is_free_preview || hasAccess;
                return (
                  <button
                    key={v.id}
                    disabled={!unlocked}
                    onClick={() => setActiveVideo(v.video_url)}
                    className="flex w-full items-center gap-3 rounded-xl border border-border bg-secondary/30 px-3.5 py-2.5 text-left text-sm transition-colors hover:bg-secondary/60 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-secondary text-xs font-semibold text-muted-foreground">
                      {i + 1}
                    </span>
                    {unlocked ? <PlayCircle className="size-4 shrink-0 text-primary" /> : <Lock className="size-4 shrink-0 text-muted-foreground" />}
                    <span className="flex-1 truncate">{v.title}</span>
                    {v.is_free_preview && <Badge variant="outline">aperçu</Badge>}
                  </button>
                );
              })}
            </div>
          </Card>
        )}

        {reviews && reviews.length > 0 && (
          <Card className="mt-4 p-5">
            <h2 className="font-display text-sm font-semibold">Avis ({reviews.length})</h2>
            <div className="mt-3 space-y-3">
              {reviews.slice(0, 5).map((r) => (
                <div key={r.id} className="border-t border-border/60 pt-3 first:border-t-0 first:pt-0">
                  <div className="flex items-center gap-1 text-accent">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star key={i} className={`size-3.5 ${i < r.rating ? "fill-current" : "opacity-25"}`} />
                    ))}
                  </div>
                  {r.comment && <p className="mt-1 text-sm text-muted-foreground">{r.comment}</p>}
                </div>
              ))}
            </div>
          </Card>
        )}
      </FadeIn>
    </div>
  );
}
