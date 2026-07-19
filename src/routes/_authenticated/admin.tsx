import { createFileRoute } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";
import { ComingSoon } from "@/components/dashboard/coming-soon";

export const Route = createFileRoute("/_authenticated/admin")({
  component: () => (
    <ComingSoon
      icon={ShieldCheck}
      title="Admin"
      body="Modération de la communauté et gestion de l'archive arrivent en Phase 5."
    />
  ),
});
