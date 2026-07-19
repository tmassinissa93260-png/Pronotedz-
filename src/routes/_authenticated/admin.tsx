import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ShieldCheck, Check, X, FileText, EyeOff, CircleCheck } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useModerateArchiveEntry } from "@/hooks/use-moderate-archive";
import { pendingSubmissionsQueryOptions } from "@/lib/queries/archive";
import { openReportsQueryOptions } from "@/lib/queries/moderation";
import { useResolveReport } from "@/hooks/use-moderation-actions";
import { supabase } from "@/lib/supabase/client";

export const Route = createFileRoute("/_authenticated/admin")({
  component: AdminPage,
});

function AdminPage() {
  const { data: userData, isLoading: userLoading } = useCurrentUser();
  const isAdmin = userData?.roles.includes("admin") ?? false;

  if (userLoading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <Skeleton className="h-9 w-64" />
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
        <ShieldCheck className="size-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Cette page est réservée aux administrateurs.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Modération</h1>
      <Tabs defaultValue="archive" className="mt-6">
        <TabsList>
          <TabsTrigger value="archive">Annales</TabsTrigger>
          <TabsTrigger value="reports">Signalements</TabsTrigger>
        </TabsList>
        <TabsContent value="archive">
          <ArchiveQueue />
        </TabsContent>
        <TabsContent value="reports">
          <ReportsQueue />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ArchiveQueue() {
  const { data: pending, isLoading } = useQuery(pendingSubmissionsQueryOptions());
  const moderate = useModerateArchiveEntry();

  async function openFile(path: string) {
    const { data, error } = await supabase.storage.from("exam-archive").createSignedUrl(path, 3600);
    if (error) return toast.error("Impossible d'ouvrir ce fichier.");
    window.open(data.signedUrl, "_blank", "noopener");
  }

  async function handle(id: string, status: "published" | "rejected") {
    try {
      await moderate.mutateAsync({ id, status });
      toast.success(status === "published" ? "Publié dans l'archive." : "Rejeté.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action impossible.");
    }
  }

  return (
    <div>
      <p className="mt-1 text-sm text-muted-foreground">Sujets envoyés par la communauté, en attente de vérification.</p>
      <div className="mt-4">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        ) : pending && pending.length > 0 ? (
          <StaggerGroup className="space-y-3">
            {pending.map((entry) => (
              <StaggerItem key={entry.id}>
                <Card className="p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold">{entry.title}</h3>
                    <Badge variant="secondary">{entry.exam_type.toUpperCase()}</Badge>
                    <Badge variant="outline">{entry.year}</Badge>
                    {entry.filiere && <Badge variant="outline">{entry.filiere.replace(/_/g, " ")}</Badge>}
                    {entry.session && <Badge variant="outline">{entry.session}</Badge>}
                  </div>
                  <p className="mt-1 text-xs capitalize text-muted-foreground">{entry.subject.replace(/_/g, " ")}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => openFile(entry.pdf_url)}>
                      <FileText className="size-4" /> Voir le sujet
                    </Button>
                    {entry.correction_url && (
                      <Button size="sm" variant="outline" onClick={() => openFile(entry.correction_url!)}>
                        <FileText className="size-4" /> Voir la correction
                      </Button>
                    )}
                    <Button size="sm" onClick={() => handle(entry.id, "published")} disabled={moderate.isPending}>
                      <Check className="size-4" /> Publier
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      onClick={() => handle(entry.id, "rejected")}
                      disabled={moderate.isPending}
                    >
                      <X className="size-4" /> Rejeter
                    </Button>
                  </div>
                </Card>
              </StaggerItem>
            ))}
          </StaggerGroup>
        ) : (
          <p className="text-sm text-muted-foreground">Aucun envoi en attente.</p>
        )}
      </div>
    </div>
  );
}

const TARGET_LABEL: Record<string, string> = { thread: "Discussion", post: "Réponse" };

function ReportsQueue() {
  const { data: reports, isLoading } = useQuery(openReportsQueryOptions());
  const resolve = useResolveReport();

  async function handle(report: NonNullable<typeof reports>[number], hide: boolean) {
    try {
      await resolve.mutateAsync({ report, hide });
      toast.success(hide ? "Contenu masqué." : "Signalement classé sans suite.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action impossible.");
    }
  }

  return (
    <div>
      <p className="mt-1 text-sm text-muted-foreground">Discussions et réponses signalées par la communauté.</p>
      <div className="mt-4">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        ) : reports && reports.length > 0 ? (
          <StaggerGroup className="space-y-3">
            {reports.map((r) => (
              <StaggerItem key={r.id}>
                <Card className="p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{TARGET_LABEL[r.target_type] ?? r.target_type}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleDateString("fr-DZ")}
                    </span>
                  </div>
                  <p className="mt-2 text-sm">{r.reason}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="destructive" onClick={() => handle(r, true)} disabled={resolve.isPending}>
                      <EyeOff className="size-4" /> Masquer le contenu
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => handle(r, false)} disabled={resolve.isPending}>
                      <CircleCheck className="size-4" /> Classer sans suite
                    </Button>
                  </div>
                </Card>
              </StaggerItem>
            ))}
          </StaggerGroup>
        ) : (
          <p className="text-sm text-muted-foreground">Aucun signalement en attente.</p>
        )}
      </div>
    </div>
  );
}
