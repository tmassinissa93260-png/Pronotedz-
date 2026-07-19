import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Star, MapPin, ShieldCheck, CalendarDays } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { FadeIn } from "@/components/motion/fade-in";
import { teacherProfileQueryOptions, teacherAvailabilityQueryOptions, teacherReviewsQueryOptions } from "@/lib/queries/teachers";

export const Route = createFileRoute("/_authenticated/teachers/$teacherId")({
  component: TeacherProfilePage,
});

const DAYS = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];

function TeacherProfilePage() {
  const { teacherId } = Route.useParams();
  const { data: teacher, isLoading } = useQuery(teacherProfileQueryOptions(teacherId));
  const { data: availability } = useQuery(teacherAvailabilityQueryOptions(teacherId));
  const { data: reviews } = useQuery(teacherReviewsQueryOptions(teacherId));

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (!teacher) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6">
        <p className="text-sm text-muted-foreground">Professeur introuvable.</p>
      </div>
    );
  }

  const availabilityByDay = new Map<number, typeof availability>();
  for (const slot of availability ?? []) {
    const list = availabilityByDay.get(slot.day_of_week) ?? [];
    list.push(slot);
    availabilityByDay.set(slot.day_of_week, list);
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <BreadcrumbNav items={[{ label: "Profs en direct", to: "/teachers" }, { label: teacher.profile?.full_name ?? "Professeur" }]} />

      <FadeIn>
        <Card className="mt-2 p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-4">
              <Avatar className="size-16">
                <AvatarImage src={teacher.profile?.avatar_url ?? undefined} />
                <AvatarFallback className="text-lg">{(teacher.profile?.full_name ?? "?").charAt(0)}</AvatarFallback>
              </Avatar>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="font-display text-xl font-bold">{teacher.profile?.full_name ?? "Professeur"}</h1>
                  {teacher.verification_status === "verified" && (
                    <ShieldCheck className="size-4 text-primary" aria-label="Vérifié" />
                  )}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                  <span className="inline-flex items-center gap-1 font-medium text-accent">
                    <Star className="size-3.5 fill-current" /> {Number(teacher.rating_avg).toFixed(1)} ({teacher.total_students} élèves)
                  </span>
                  {teacher.profile?.wilaya && (
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="size-3.5" /> {teacher.profile.wilaya}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <Button asChild size="lg">
              <Link to="/sessions/book/$teacherId" params={{ teacherId }}>
                <CalendarDays className="size-4" /> Voir les créneaux
              </Link>
            </Button>
          </div>

          {teacher.bio && <p className="mt-5 text-sm leading-relaxed text-muted-foreground">{teacher.bio}</p>}

          <div className="mt-5 flex flex-wrap gap-1.5">
            {teacher.subjects.map((s) => (
              <Badge key={s}>{s}</Badge>
            ))}
          </div>
        </Card>

        {availability && availability.length > 0 && (
          <Card className="mt-4 p-6">
            <h2 className="font-display text-sm font-semibold">Disponibilités habituelles</h2>
            <div className="mt-3 space-y-2">
              {[...availabilityByDay.entries()].map(([day, slots]) => (
                <div key={day} className="flex items-center gap-3 text-sm">
                  <span className="w-24 shrink-0 text-muted-foreground">{DAYS[day]}</span>
                  <div className="flex flex-wrap gap-1.5">
                    {slots?.map((s) => (
                      <Badge key={s.id} variant="outline">
                        {s.start_time.slice(0, 5)}–{s.end_time.slice(0, 5)}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Indicatif — réserve un créneau publié pour confirmer une session.
            </p>
          </Card>
        )}

        {reviews && reviews.length > 0 && (
          <Card className="mt-4 p-6">
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
