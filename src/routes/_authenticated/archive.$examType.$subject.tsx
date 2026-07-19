import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileText, ClipboardCheck } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { entriesQueryOptions, type ExamType } from "@/lib/queries/archive";
import { supabase } from "@/lib/supabase/client";

type Search = { filiere?: string };

export const Route = createFileRoute("/_authenticated/archive/$examType/$subject")({
  validateSearch: (s: Record<string, unknown>): Search => ({
    filiere: typeof s.filiere === "string" ? s.filiere : undefined,
  }),
  component: EntriesList,
});

function useOpenFile() {
  return useMutation({
    mutationFn: async (path: string) => {
      const { data, error } = await supabase.storage.from("exam-archive").createSignedUrl(path, 3600);
      if (error) throw error;
      return data.signedUrl;
    },
    onSuccess: (url) => window.open(url, "_blank", "noopener"),
    onError: () => toast.error("Impossible d'ouvrir ce fichier pour le moment."),
  });
}

const SESSION_LABEL: Record<string, string> = { normale: "Session normale", rattrapage: "Rattrapage" };

function EntriesList() {
  const { examType, subject } = Route.useParams();
  const { filiere } = Route.useSearch();
  const type = examType as ExamType;
  const { data: entries, isLoading } = useQuery(entriesQueryOptions(type, filiere ?? null, subject));
  const openFile = useOpenFile();

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <BreadcrumbNav
        items={[
          { label: "Archive", to: "/archive" },
          { label: type.toUpperCase(), to: "/archive/$examType", params: { examType } },
          { label: subject.replace(/_/g, " ") },
        ]}
      />
      <h1 className="mt-2 font-display text-2xl font-bold capitalize tracking-tight sm:text-3xl">
        {subject.replace(/_/g, " ")}
      </h1>

      <div className="mt-8 space-y-3">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)
        ) : entries && entries.length > 0 ? (
          <StaggerGroup className="space-y-3">
            {entries.map((entry) => (
              <StaggerItem key={entry.id}>
                <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold">{entry.title}</h3>
                      <Badge variant="secondary">{entry.year}</Badge>
                      {entry.session && <Badge variant="outline">{SESSION_LABEL[entry.session] ?? entry.session}</Badge>}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openFile.mutate(entry.pdf_url)}
                      disabled={openFile.isPending}
                    >
                      <FileText className="size-4" /> Sujet
                    </Button>
                    {entry.correction_url && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openFile.mutate(entry.correction_url!)}
                        disabled={openFile.isPending}
                      >
                        <ClipboardCheck className="size-4" /> Correction
                      </Button>
                    )}
                  </div>
                </Card>
              </StaggerItem>
            ))}
          </StaggerGroup>
        ) : (
          <p className="text-sm text-muted-foreground">Aucun sujet publié pour cette matière pour le moment.</p>
        )}
      </div>
    </div>
  );
}
