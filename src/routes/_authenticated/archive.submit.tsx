import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { UploadCloud, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { useSubmitArchive } from "@/hooks/use-submit-archive";
import type { ExamType } from "@/lib/queries/archive";

export const Route = createFileRoute("/_authenticated/archive/submit")({
  component: SubmitArchive,
});

function SubmitArchive() {
  const navigate = useNavigate();
  const submit = useSubmitArchive();

  const [examType, setExamType] = useState<ExamType>("bac");
  const [year, setYear] = useState(new Date().getFullYear());
  const [subject, setSubject] = useState("");
  const [filiere, setFiliere] = useState("");
  const [session, setSession] = useState<"normale" | "rattrapage" | "">("");
  const [title, setTitle] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [correctionFile, setCorrectionFile] = useState<File | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!pdfFile) {
      toast.error("Ajoute le fichier du sujet (PDF ou image).");
      return;
    }
    try {
      await submit.mutateAsync({
        examType,
        year,
        subject,
        filiere: examType === "bac" && filiere ? filiere : null,
        session: session || null,
        title,
        pdfFile,
        correctionFile,
      });
      toast.success("Merci ! Ton sujet est envoyé pour vérification avant publication.");
      navigate({ to: "/archive" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible d'envoyer ce sujet pour le moment.");
    }
  }

  return (
    <div className="mx-auto max-w-xl px-4 py-8 sm:px-6">
      <BreadcrumbNav items={[{ label: "Archive", to: "/archive" }, { label: "Envoyer un sujet" }]} />
      <h1 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">Envoyer un sujet</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Tu as un sujet ou une correction que l'archive n'a pas encore ? Envoie-le — un admin le vérifie avant
        qu'il soit visible pour tout le monde.
      </p>

      <Card className="mt-6 p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Examen</Label>
              <Select value={examType} onValueChange={(v) => setExamType(v as ExamType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bem">BEM</SelectItem>
                  <SelectItem value="bac">BAC</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="year">Année</Label>
              <Input
                id="year"
                type="number"
                min={2000}
                max={2100}
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                required
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="subject">Matière</Label>
            <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Mathématiques" required />
          </div>

          {examType === "bac" && (
            <div className="space-y-1.5">
              <Label htmlFor="filiere">
                Filière <span className="font-normal text-muted-foreground">(optionnel)</span>
              </Label>
              <Input id="filiere" value={filiere} onChange={(e) => setFiliere(e.target.value)} placeholder="Sciences expérimentales" />
            </div>
          )}

          <div className="space-y-1.5">
            <Label>
              Session <span className="font-normal text-muted-foreground">(optionnel)</span>
            </Label>
            <Select value={session} onValueChange={(v) => setSession(v as typeof session)}>
              <SelectTrigger>
                <SelectValue placeholder="Non précisé" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="normale">Session normale</SelectItem>
                <SelectItem value="rattrapage">Rattrapage</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="title">Titre</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="BAC 2025 — Mathématiques, session normale" required />
          </div>

          <FileInput label="Sujet (PDF ou image)" file={pdfFile} onChange={setPdfFile} />
          <FileInput label="Correction (optionnel)" file={correctionFile} onChange={setCorrectionFile} />

          <div className="flex items-start gap-2 rounded-xl border border-border bg-secondary/30 p-3 text-xs text-muted-foreground">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
            Rien n'est publié directement — un admin vérifie chaque envoi avant qu'il apparaisse dans l'archive.
          </div>

          <Button type="submit" disabled={submit.isPending} className="w-full">
            {submit.isPending ? "Envoi…" : "Envoyer pour vérification"}
          </Button>
        </form>
      </Card>
    </div>
  );
}

function FileInput({ label, file, onChange }: { label: string; file: File | null; onChange: (f: File | null) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-border bg-background px-3 py-2.5 text-sm hover:bg-secondary/40">
      <UploadCloud className="size-4 shrink-0 text-primary" />
      <div className="flex-1">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="font-medium">{file?.name ?? "Choisir un fichier"}</div>
      </div>
      <input
        type="file"
        accept="application/pdf,image/*"
        className="hidden"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}
