import { createFileRoute, Link } from "@tanstack/react-router";
import { GraduationCap, Award } from "lucide-react";
import { Card } from "@/components/ui/card";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";

export const Route = createFileRoute("/_authenticated/archive/")({
  component: ArchiveExamTypePicker,
});

function ArchiveExamTypePicker() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Archive BAC &amp; BEM</h1>
      <p className="mt-1 text-muted-foreground">Sujets et corrections des sessions précédentes.</p>

      <StaggerGroup className="mt-8 grid gap-4 sm:grid-cols-2">
        <StaggerItem>
          <Link to="/archive/$examType" params={{ examType: "bem" }}>
            <Card className="hover-lift h-full p-6">
              <div className="grid size-12 place-items-center rounded-2xl bg-primary/12 text-primary">
                <Award className="size-6" />
              </div>
              <h2 className="mt-4 font-display text-lg font-semibold">BEM</h2>
              <p className="mt-1 text-sm text-muted-foreground">4e année moyenne</p>
            </Card>
          </Link>
        </StaggerItem>
        <StaggerItem>
          <Link to="/archive/$examType" params={{ examType: "bac" }}>
            <Card className="hover-lift h-full p-6">
              <div className="grid size-12 place-items-center rounded-2xl bg-accent/12 text-accent">
                <GraduationCap className="size-6" />
              </div>
              <h2 className="mt-4 font-display text-lg font-semibold">BAC</h2>
              <p className="mt-1 text-sm text-muted-foreground">3e année secondaire, 7 filières</p>
            </Card>
          </Link>
        </StaggerItem>
      </StaggerGroup>

      <Link to="/archive/submit" className="mt-8 inline-block text-sm font-medium text-primary hover:underline">
        Tu as un sujet qui manque ? Envoie-le →
      </Link>
    </div>
  );
}
