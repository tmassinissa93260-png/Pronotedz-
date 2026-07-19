import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Plus, Trash2, Eye } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { courseQueryOptions, courseVideosQueryOptions } from "@/lib/queries/courses";
import { useAddCourseVideo, useDeleteCourseVideo, useSetCourseStatus } from "@/hooks/use-course-actions";

export const Route = createFileRoute("/_authenticated/teacher/courses/$courseId")({
  component: ManageCourseVideos,
});

function ManageCourseVideos() {
  const { courseId } = Route.useParams();
  const { user } = Route.useRouteContext();
  const { data: course, isLoading: courseLoading } = useQuery(courseQueryOptions(courseId));
  const { data: videos, isLoading: videosLoading } = useQuery(courseVideosQueryOptions(courseId));
  const addVideo = useAddCourseVideo(courseId);
  const deleteVideo = useDeleteCourseVideo(courseId);
  const setStatus = useSetCourseStatus(user.id);

  const [title, setTitle] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [isFreePreview, setIsFreePreview] = useState(false);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!title || !videoUrl) {
      toast.error("Titre et URL de la vidéo requis.");
      return;
    }
    try {
      await addVideo.mutateAsync({
        title,
        videoUrl,
        durationSec: null,
        orderIndex: videos?.length ?? 0,
        isFreePreview,
      });
      setTitle("");
      setVideoUrl("");
      setIsFreePreview(false);
      toast.success("Vidéo ajoutée.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible d'ajouter cette vidéo.");
    }
  }

  async function togglePublish() {
    if (!course) return;
    try {
      await setStatus.mutateAsync({ courseId, status: course.status === "published" ? "draft" : "published" });
      toast.success(course.status === "published" ? "Cours dépublié." : "Cours publié.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action impossible.");
    }
  }

  if (courseLoading) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
        <Skeleton className="h-9 w-64" />
      </div>
    );
  }
  if (!course) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center sm:px-6">
        <p className="text-sm text-muted-foreground">Cours introuvable.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <Link to="/teacher/courses" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Mes cours
      </Link>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">{course.title}</h1>
          <Badge variant={course.status === "published" ? "default" : "secondary"} className="mt-2">
            {course.status === "published" ? "Publié" : "Brouillon"}
          </Badge>
        </div>
        <Button onClick={togglePublish} disabled={setStatus.isPending}>
          {course.status === "published" ? "Dépublier" : "Publier le cours"}
        </Button>
      </div>

      <Card className="mt-6 p-5">
        <h2 className="font-display text-sm font-semibold">Ajouter une vidéo</h2>
        <form onSubmit={handleAdd} className="mt-3 space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="vtitle">Titre</Label>
            <Input id="vtitle" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="vurl">URL de la vidéo</Label>
            <Input id="vurl" value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} placeholder="https://…" required />
          </div>
          <div className="flex items-center gap-2.5">
            <Switch id="preview" checked={isFreePreview} onCheckedChange={setIsFreePreview} />
            <Label htmlFor="preview" className="font-normal">
              Aperçu gratuit (visible sans inscription)
            </Label>
          </div>
          <Button type="submit" disabled={addVideo.isPending}>
            <Plus className="size-4" /> Ajouter
          </Button>
        </form>
      </Card>

      <div className="mt-6 space-y-2">
        {videosLoading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14" />)
        ) : videos && videos.length > 0 ? (
          videos.map((v, i) => (
            <Card key={v.id} className="flex items-center justify-between p-3.5">
              <div className="flex items-center gap-2.5 text-sm">
                <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-secondary text-xs font-semibold text-muted-foreground">
                  {i + 1}
                </span>
                <span>{v.title}</span>
                {v.is_free_preview && (
                  <Badge variant="outline">
                    <Eye className="size-3" /> aperçu
                  </Badge>
                )}
              </div>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => deleteVideo.mutate(v.id)}
                disabled={deleteVideo.isPending}
                aria-label="Supprimer"
              >
                <Trash2 className="size-4 text-destructive" />
              </Button>
            </Card>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">Aucune vidéo pour l'instant.</p>
        )}
      </div>
    </div>
  );
}
