import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { memoSheetQueryOptions } from "@/lib/queries/tools";

export const Route = createFileRoute("/_authenticated/tools/memo/$sheetId")({
  component: MemoSheetDetail,
});

type Block = { type: "summary"; content: string } | { type: "flashcard"; front: string; back: string };

function MemoSheetDetail() {
  const { sheetId } = Route.useParams();
  const { data: sheet, isLoading } = useQuery(memoSheetQueryOptions(sheetId));

  if (isLoading) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
        <Skeleton className="h-9 w-64" />
      </div>
    );
  }
  if (!sheet) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center sm:px-6">
        <p className="text-sm text-muted-foreground">Fiche introuvable.</p>
      </div>
    );
  }

  const blocks = (sheet.blocks as Block[] | null) ?? [];
  const summary = blocks.find((b) => b.type === "summary") as Extract<Block, { type: "summary" }> | undefined;
  const flashcards = blocks.filter((b) => b.type === "flashcard") as Extract<Block, { type: "flashcard" }>[];

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <BreadcrumbNav items={[{ label: "Mémos & fiches", to: "/tools/memo" }, { label: sheet.title }]} />
      <h1 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">{sheet.title}</h1>

      {summary && (
        <Card className="mt-6 p-5">
          <h2 className="font-display text-sm font-semibold">Résumé</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{summary.content}</p>
        </Card>
      )}

      {flashcards.length > 0 && (
        <div className="mt-6">
          <h2 className="font-display text-sm font-semibold">Flashcards ({flashcards.length})</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {flashcards.map((card, i) => (
              <Flashcard key={i} front={card.front} back={card.back} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Flashcard({ front, back }: { front: string; back: string }) {
  const [flipped, setFlipped] = useState(false);
  return (
    <button
      onClick={() => setFlipped((f) => !f)}
      className="text-left"
      style={{ perspective: 1000 }}
      aria-label="Retourner la carte"
    >
      <motion.div
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        style={{ transformStyle: "preserve-3d" }}
        className="relative h-32"
      >
        <Card className="absolute inset-0 flex items-center justify-center p-4 text-center text-sm font-medium" style={{ backfaceVisibility: "hidden" }}>
          {front}
        </Card>
        <Card
          className="absolute inset-0 flex items-center justify-center bg-primary/8 p-4 text-center text-sm text-muted-foreground"
          style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}
        >
          {back}
        </Card>
      </motion.div>
    </button>
  );
}
