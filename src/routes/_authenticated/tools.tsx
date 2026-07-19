import { createFileRoute } from "@tanstack/react-router";
import { Wrench } from "lucide-react";
import { ComingSoon } from "@/components/dashboard/coming-soon";

export const Route = createFileRoute("/_authenticated/tools")({
  component: () => (
    <ComingSoon
      icon={Wrench}
      title="Outils"
      body="Calculatrice, compte à rebours, aide aux devoirs et mémos arrivent en Phase 4."
    />
  ),
});
