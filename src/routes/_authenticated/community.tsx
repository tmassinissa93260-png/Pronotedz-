import { createFileRoute } from "@tanstack/react-router";
import { MessageSquare } from "lucide-react";
import { ComingSoon } from "@/components/dashboard/coming-soon";

export const Route = createFileRoute("/_authenticated/community")({
  component: () => (
    <ComingSoon icon={MessageSquare} title="Communauté" body="Le forum communautaire arrive en Phase 4." />
  ),
});
