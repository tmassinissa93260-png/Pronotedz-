import { createFileRoute } from "@tanstack/react-router";
import { Archive } from "lucide-react";
import { ComingSoon } from "@/components/dashboard/coming-soon";

export const Route = createFileRoute("/_authenticated/archive")({
  component: () => (
    <ComingSoon
      icon={Archive}
      title="Archive BAC & BEM"
      body="Consultation des 315 annales par niveau, matière et année arrive en Phase 2."
    />
  ),
});
