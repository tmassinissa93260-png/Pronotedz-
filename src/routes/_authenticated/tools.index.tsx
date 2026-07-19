import { createFileRoute, Link } from "@tanstack/react-router";
import { Calculator, Timer, Camera, NotebookPen } from "lucide-react";
import { Card } from "@/components/ui/card";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";

export const Route = createFileRoute("/_authenticated/tools/")({
  component: ToolsIndex,
});

const TOOLS = [
  { to: "/tools/calculator" as const, icon: Calculator, title: "Calculatrice", body: "Calculatrice scientifique complète." },
  { to: "/tools/countdown" as const, icon: Timer, title: "Compte à rebours", body: "Le temps qu'il te reste avant ton examen." },
  { to: "/tools/homework" as const, icon: Camera, title: "Aide aux devoirs", body: "Photographie un exercice, l'IA t'explique." },
  { to: "/tools/memo" as const, icon: NotebookPen, title: "Mémos & fiches", body: "Fiches de révision générées par l'IA." },
];

function ToolsIndex() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Outils</h1>
      <p className="mt-1 text-muted-foreground">Tout ce qu'il faut pour réviser efficacement.</p>

      <StaggerGroup className="mt-8 grid gap-4 sm:grid-cols-2">
        {TOOLS.map((tool) => (
          <StaggerItem key={tool.to}>
            <Link to={tool.to}>
              <Card className="hover-lift flex h-full items-start gap-4 p-5">
                <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-primary/12 text-primary">
                  <tool.icon className="size-5" />
                </div>
                <div>
                  <h2 className="font-display text-sm font-semibold">{tool.title}</h2>
                  <p className="mt-1 text-xs text-muted-foreground">{tool.body}</p>
                </div>
              </Card>
            </Link>
          </StaggerItem>
        ))}
      </StaggerGroup>
    </div>
  );
}
