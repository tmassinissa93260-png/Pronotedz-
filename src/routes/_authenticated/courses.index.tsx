import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Search, Star, PlayCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { publishedCoursesQueryOptions } from "@/lib/queries/courses";

export const Route = createFileRoute("/_authenticated/courses/")({
  component: CoursesMarketplace,
});

function CoursesMarketplace() {
  const [subject, setSubject] = useState("");
  const { data: courses, isLoading } = useQuery(publishedCoursesQueryOptions(subject));

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Cours de profs</h1>
      <p className="mt-1 text-muted-foreground">Cours vidéo créés par des professeurs, à ton rythme.</p>

      <div className="relative mt-6 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Rechercher une matière…" className="pl-9" />
      </div>

      {isLoading ? (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-52" />
          ))}
        </div>
      ) : courses && courses.length > 0 ? (
        <StaggerGroup className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {courses.map((course) => (
            <StaggerItem key={course.id}>
              <Link to="/courses/$courseId" params={{ courseId: course.id }}>
                <Card className="hover-lift flex h-full flex-col overflow-hidden">
                  <div className="grid aspect-video place-items-center bg-secondary/60 text-muted-foreground">
                    {course.thumbnail_url ? (
                      <img src={course.thumbnail_url} alt="" className="size-full object-cover" />
                    ) : (
                      <PlayCircle className="size-8" />
                    )}
                  </div>
                  <div className="flex flex-1 flex-col p-4">
                    <Badge variant="secondary" className="w-fit">
                      {course.subject}
                    </Badge>
                    <h2 className="mt-2 font-display text-sm font-semibold leading-snug">{course.title}</h2>
                    <p className="mt-1 truncate text-xs text-muted-foreground">{course.teacher?.full_name ?? "Professeur"}</p>
                    <div className="mt-auto flex items-center justify-between pt-3 text-sm">
                      <span className="inline-flex items-center gap-1 font-medium text-accent">
                        <Star className="size-3.5 fill-current" /> {Number(course.rating_avg).toFixed(1)}
                      </span>
                      <span className="font-display font-bold text-primary">
                        {course.price > 0 ? `${Number(course.price).toLocaleString()} DZD` : "Gratuit"}
                      </span>
                    </div>
                  </div>
                </Card>
              </Link>
            </StaggerItem>
          ))}
        </StaggerGroup>
      ) : (
        <p className="mt-10 text-sm text-muted-foreground">Aucun cours publié pour le moment.</p>
      )}
    </div>
  );
}
