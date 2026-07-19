import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCreateCourse } from "@/hooks/use-course-actions";
import { ALL_TEACHABLE_LEVELS } from "@/lib/curriculum/school-levels";
import type { Database } from "@/lib/supabase/types";

type SchoolLevel = Database["public"]["Enums"]["school_level"];
type PriceType = Database["public"]["Enums"]["price_type"];

export const Route = createFileRoute("/_authenticated/teacher/courses/new")({
  component: NewCoursePage,
});

function NewCoursePage() {
  const { user } = Route.useRouteContext();
  const navigate = useNavigate();
  const create = useCreateCourse(user.id);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [subject, setSubject] = useState("");
  const [level, setLevel] = useState<SchoolLevel>("lycee_3_sciences");
  const [priceType, setPriceType] = useState<PriceType>("series");
  const [price, setPrice] = useState(0);
  const [trailerUrl, setTrailerUrl] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title || !subject || !trailerUrl) {
      toast.error("Renseigne au moins le titre, la matière et une vidéo bande-annonce.");
      return;
    }
    try {
      const { id } = await create.mutateAsync({
        title,
        description: description || null,
        subject,
        level,
        language: "fr",
        price,
        priceType,
        trailerVideoUrl: trailerUrl,
        thumbnailUrl: null,
      });
      toast.success("Cours créé — ajoute des vidéos avant de le publier.");
      navigate({ to: "/teacher/courses/$courseId", params: { courseId: id } });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de créer ce cours.");
    }
  }

  return (
    <div className="mx-auto max-w-xl px-4 py-8 sm:px-6">
      <Link to="/teacher/courses" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Mes cours
      </Link>
      <h1 className="mt-3 font-display text-2xl font-bold tracking-tight sm:text-3xl">Nouveau cours</h1>

      <Card className="mt-6 p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="title">Titre</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="description">
              Description <span className="font-normal text-muted-foreground">(optionnel)</span>
            </Label>
            <Textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} rows={4} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="subject">Matière</Label>
              <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label>Niveau</Label>
              <Select value={level} onValueChange={(v) => setLevel(v as SchoolLevel)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ALL_TEACHABLE_LEVELS.map((l) => (
                    <SelectItem key={l.schoolLevel} value={l.schoolLevel}>
                      {l.label_fr}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Tarification</Label>
              <Select value={priceType} onValueChange={(v) => setPriceType(v as PriceType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="series">Prix unique</SelectItem>
                  <SelectItem value="per_session">Par vidéo</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="price">
                Prix (DZD) <span className="font-normal text-muted-foreground">(0 = gratuit)</span>
              </Label>
              <Input id="price" type="number" min={0} value={price} onChange={(e) => setPrice(Number(e.target.value))} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="trailer">Vidéo bande-annonce (URL)</Label>
            <Input id="trailer" value={trailerUrl} onChange={(e) => setTrailerUrl(e.target.value)} placeholder="https://…" required />
          </div>

          <Button type="submit" disabled={create.isPending} className="w-full">
            {create.isPending ? "Création…" : "Créer le cours (brouillon)"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
