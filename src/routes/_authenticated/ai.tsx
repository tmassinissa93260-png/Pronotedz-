import { createFileRoute } from "@tanstack/react-router";
import { Sparkles } from "lucide-react";
import { ComingSoon } from "@/components/dashboard/coming-soon";

export const Route = createFileRoute("/_authenticated/ai")({
  component: () => (
    <ComingSoon
      icon={Sparkles}
      title="Tuteur IA"
      body="Conversations persistantes, examens blancs et fiches de révision arrivent en Phase 2."
    />
  ),
});
