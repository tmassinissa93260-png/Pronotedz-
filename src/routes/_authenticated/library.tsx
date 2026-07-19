import { createFileRoute } from "@tanstack/react-router";
import { Library } from "lucide-react";
import { ComingSoon } from "@/components/dashboard/coming-soon";

export const Route = createFileRoute("/_authenticated/library")({
  component: () => (
    <ComingSoon
      icon={Library}
      title="Programme officiel"
      body="La bibliothèque de cours (cycle → niveau → matière → chapitre) arrive en Phase 2."
    />
  ),
});
