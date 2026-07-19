import { createFileRoute } from "@tanstack/react-router";
import { Video } from "lucide-react";
import { ComingSoon } from "@/components/dashboard/coming-soon";

export const Route = createFileRoute("/_authenticated/teachers")({
  component: () => (
    <ComingSoon
      icon={Video}
      title="Profs en direct"
      body="Réservation de créneaux et sessions live Daily.co arrivent en Phase 3."
    />
  ),
});
