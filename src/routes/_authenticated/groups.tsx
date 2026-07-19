import { createFileRoute } from "@tanstack/react-router";
import { Users } from "lucide-react";
import { ComingSoon } from "@/components/dashboard/coming-soon";

export const Route = createFileRoute("/_authenticated/groups")({
  component: () => (
    <ComingSoon icon={Users} title="Groupes d'étude" body="Groupes, annonces et quiz partagés arrivent en Phase 4." />
  ),
});
