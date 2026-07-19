import { createFileRoute } from "@tanstack/react-router";
import { GraduationCap } from "lucide-react";
import { ComingSoon } from "@/components/dashboard/coming-soon";

export const Route = createFileRoute("/_authenticated/teacher")({
  component: () => (
    <ComingSoon
      icon={GraduationCap}
      title="Espace prof"
      body="Création de cours, chapitres et gestion des réservations arrivent en Phase 3."
    />
  ),
});
