import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { Camera, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FadeIn } from "@/components/motion/fade-in";
import { useHomeworkHelp, type HomeworkResult } from "@/hooks/use-tools-ai";

export const Route = createFileRoute("/_authenticated/tools/homework")({
  component: HomeworkPage,
});

function HomeworkPage() {
  const { user } = Route.useRouteContext();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<HomeworkResult | null>(null);
  const help = useHomeworkHelp(user.id);

  function handleFile(f: File | null) {
    setFile(f);
    setResult(null);
    setPreview(f ? URL.createObjectURL(f) : null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      toast.error("Ajoute une photo de l'exercice.");
      return;
    }
    try {
      const res = await help.mutateAsync({ file, question });
      setResult(res);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible d'analyser cette photo pour le moment.");
    }
  }

  return (
    <div className="mx-auto max-w-xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-bold tracking-tight">Aide aux devoirs</h1>
      <p className="mt-1 text-muted-foreground">Photographie un exercice, l'IA t'explique la méthode.</p>

      <Card className="mt-6 p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="flex cursor-pointer flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-border bg-secondary/20 px-4 py-8 text-center hover:bg-secondary/40">
            {preview ? (
              <img src={preview} alt="Aperçu" className="max-h-56 rounded-xl object-contain" />
            ) : (
              <>
                <Camera className="size-8 text-primary" />
                <span className="text-sm text-muted-foreground">Choisir une photo</span>
              </>
            )}
            <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => handleFile(e.target.files?.[0] ?? null)} />
          </label>

          <div className="space-y-1.5">
            <Label htmlFor="question">
              Ta question <span className="font-normal text-muted-foreground">(optionnel)</span>
            </Label>
            <Input id="question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Je bloque sur la question 2…" />
          </div>

          <Button type="submit" disabled={help.isPending || !file} className="w-full">
            <Sparkles className="size-4" /> {help.isPending ? "Analyse…" : "Expliquer"}
          </Button>
        </form>
      </Card>

      {result && (
        <FadeIn>
          <Card className="mt-4 p-6">
            <h2 className="font-display text-sm font-semibold">Explication</h2>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{result.explanation}</p>
            {result.steps?.length > 0 && (
              <ol className="mt-4 space-y-2">
                {result.steps.map((step, i) => (
                  <li key={i} className="flex gap-2.5 text-sm">
                    <span className="grid size-5 shrink-0 place-items-center rounded-full bg-primary/12 text-[11px] font-semibold text-primary">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            )}
            <div className="mt-4 rounded-xl bg-primary/8 p-3.5 text-sm font-medium text-primary">{result.answer}</div>
          </Card>
        </FadeIn>
      )}
    </div>
  );
}
