import { createFileRoute } from "@tanstack/react-router";
import { BookOpen } from "lucide-react";
import { ComingSoon } from "@/components/dashboard/coming-soon";

export const Route = createFileRoute("/_authenticated/courses")({
  component: () => (
    <ComingSoon icon={BookOpen} title="Cours de profs" body="La marketplace de cours vidéo arrive en Phase 2." />
  ),
});
