import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Plus, NotebookPen, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { memoSheetsQueryOptions } from "@/lib/queries/tools";
import { useGenerateMemo } from "@/hooks/use-tools-ai";

export const Route = createFileRoute("/_authenticated/tools/memo/")({
  component: MemoIndex,
});

function MemoIndex() {
  const { user } = Route.useRouteContext();
  const { data: sheets, isLoading } = useQuery(memoSheetsQueryOptions(user.id));

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Mémos &amp; fiches</h1>
          <p className="mt-1 text-muted-foreground">Colle ton cours, l'IA en fait une fiche de révision.</p>
        </div>
        <NewMemoDialog userId={user.id} />
      </div>

      <div className="mt-8">
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        ) : sheets && sheets.length > 0 ? (
          <StaggerGroup className="grid gap-4 sm:grid-cols-2">
            {sheets.map((s) => (
              <StaggerItem key={s.id}>
                <Link to="/tools/memo/$sheetId" params={{ sheetId: s.id }}>
                  <Card className="hover-lift flex h-full items-start gap-3 p-5">
                    <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary/12 text-primary">
                      <NotebookPen className="size-4" />
                    </div>
                    <div>
                      <h2 className="font-display text-sm font-semibold">{s.title}</h2>
                      {s.subject && <p className="mt-0.5 text-xs text-muted-foreground">{s.subject}</p>}
                    </div>
                  </Card>
                </Link>
              </StaggerItem>
            ))}
          </StaggerGroup>
        ) : (
          <Card className="p-8 text-center">
            <p className="text-sm text-muted-foreground">Aucune fiche pour l'instant.</p>
          </Card>
        )}
      </div>
    </div>
  );
}

function NewMemoDialog({ userId }: { userId: string }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [sourceText, setSourceText] = useState("");
  const navigate = Route.useNavigate();
  const generate = useGenerateMemo(userId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title || !sourceText) {
      toast.error("Ajoute un titre et le texte de ton cours.");
      return;
    }
    try {
      const sheet = await generate.mutateAsync({ title, sourceText, subject: subject || undefined });
      setOpen(false);
      navigate({ to: "/tools/memo/$sheetId", params: { sheetId: sheet.id } });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de générer cette fiche pour le moment.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="size-4" /> Nouvelle fiche
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Générer une fiche</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="title">Titre</Label>
              <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="subject">
                Matière <span className="font-normal text-muted-foreground">(optionnel)</span>
              </Label>
              <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="source">Texte du cours</Label>
            <Textarea id="source" value={sourceText} onChange={(e) => setSourceText(e.target.value)} rows={8} required />
          </div>
          <Button type="submit" disabled={generate.isPending} className="w-full">
            <Sparkles className="size-4" /> {generate.isPending ? "Génération…" : "Générer la fiche"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
