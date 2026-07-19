import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Users, Star } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { useCurrentUser } from "@/hooks/use-current-user";
import { teacherCoursesQueryOptions } from "@/lib/queries/courses";
import { useSetCourseStatus } from "@/hooks/use-course-actions";

export const Route = createFileRoute("/_authenticated/teacher/courses/")({
  component: TeacherCoursesPage,
});

const STATUS_LABEL: Record<string, string> = { draft: "Brouillon", published: "Publié", archived: "Archivé" };

function TeacherCoursesPage() {
  const { user } = Route.useRouteContext();
  const { data: userData, isLoading: userLoading } = useCurrentUser();
  const isTeacher = userData?.roles.includes("teacher") ?? false;

  if (userLoading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <Skeleton className="h-9 w-64" />
      </div>
    );
  }
  if (!isTeacher) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
        <p className="text-sm text-muted-foreground">Cette page est réservée aux profs.</p>
      </div>
    );
  }

  return <CourseList teacherId={user.id} />;
}

function CourseList({ teacherId }: { teacherId: string }) {
  const { data: courses, isLoading } = useQuery(teacherCoursesQueryOptions(teacherId));
  const setStatus = useSetCourseStatus(teacherId);

  async function togglePublish(courseId: string, current: string) {
    try {
      await setStatus.mutateAsync({ courseId, status: current === "published" ? "draft" : "published" });
      toast.success(current === "published" ? "Cours dépublié." : "Cours publié.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action impossible.");
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Mes cours</h1>
          <p className="mt-1 text-muted-foreground">Crée un cours vidéo et publie-le quand il est prêt.</p>
        </div>
        <Button asChild>
          <Link to="/teacher/courses/new">
            <Plus className="size-4" /> Nouveau cours
          </Link>
        </Button>
      </div>

      <div className="mt-8 space-y-3">
        {isLoading ? (
          Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        ) : courses && courses.length > 0 ? (
          <StaggerGroup className="space-y-3">
            {courses.map((course) => (
              <StaggerItem key={course.id}>
                <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold">{course.title}</h3>
                      <Badge variant={course.status === "published" ? "default" : "secondary"}>
                        {STATUS_LABEL[course.status]}
                      </Badge>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <Users className="size-3" /> {course.enrolled_count}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Star className="size-3 fill-current text-accent" /> {Number(course.rating_avg).toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" asChild>
                      <Link to="/teacher/courses/$courseId" params={{ courseId: course.id }}>
                        Gérer les vidéos
                      </Link>
                    </Button>
                    <Button
                      size="sm"
                      variant={course.status === "published" ? "ghost" : "default"}
                      onClick={() => togglePublish(course.id, course.status)}
                      disabled={setStatus.isPending}
                    >
                      {course.status === "published" ? "Dépublier" : "Publier"}
                    </Button>
                  </div>
                </Card>
              </StaggerItem>
            ))}
          </StaggerGroup>
        ) : (
          <Card className="p-8 text-center">
            <p className="text-sm text-muted-foreground">Aucun cours pour l'instant.</p>
          </Card>
        )}
      </div>
    </div>
  );
}
