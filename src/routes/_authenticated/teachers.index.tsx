import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Star, MapPin, Search } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { teachersQueryOptions } from "@/lib/queries/teachers";

export const Route = createFileRoute("/_authenticated/teachers/")({
  component: TeachersMarketplace,
});

function TeachersMarketplace() {
  const [subject, setSubject] = useState("");
  const { data: teachers, isLoading } = useQuery(teachersQueryOptions(subject));

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Profs en direct</h1>
      <p className="mt-1 text-muted-foreground">Réserve une session 1-à-1 en visio avec un professeur vérifié.</p>

      <div className="relative mt-6 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="Rechercher une matière…"
          className="pl-9"
        />
      </div>

      {isLoading ? (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : teachers && teachers.length > 0 ? (
        <StaggerGroup className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {teachers.map((teacher) => (
            <StaggerItem key={teacher.user_id}>
              <Link to="/teachers/$teacherId" params={{ teacherId: teacher.user_id }}>
                <Card className="hover-lift flex h-full flex-col gap-3 p-5">
                  <div className="flex items-center gap-3">
                    <Avatar className="size-11">
                      <AvatarImage src={teacher.profile?.avatar_url ?? undefined} />
                      <AvatarFallback>{(teacher.profile?.full_name ?? "?").charAt(0)}</AvatarFallback>
                    </Avatar>
                    <div className="min-w-0">
                      <h2 className="truncate font-display text-sm font-semibold">
                        {teacher.profile?.full_name ?? "Professeur"}
                      </h2>
                      {teacher.profile?.wilaya && (
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                          <MapPin className="size-3" /> {teacher.profile.wilaya}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {teacher.subjects.slice(0, 3).map((s) => (
                      <Badge key={s} variant="secondary">
                        {s}
                      </Badge>
                    ))}
                  </div>
                  <div className="mt-auto flex items-center justify-between pt-2 text-sm">
                    <span className="inline-flex items-center gap-1 font-medium text-accent">
                      <Star className="size-3.5 fill-current" /> {Number(teacher.rating_avg).toFixed(1)}
                    </span>
                    {teacher.hourly_rate != null && (
                      <span className="font-semibold text-primary">
                        {Number(teacher.hourly_rate).toLocaleString()} DZD/h
                      </span>
                    )}
                  </div>
                </Card>
              </Link>
            </StaggerItem>
          ))}
        </StaggerGroup>
      ) : (
        <p className="mt-10 text-sm text-muted-foreground">Aucun professeur vérifié pour le moment.</p>
      )}
    </div>
  );
}
