import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Search, Plus, MessageSquare } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { threadsQueryOptions } from "@/lib/queries/community";
import { useCreateThread } from "@/hooks/use-community-actions";

export const Route = createFileRoute("/_authenticated/community/")({
  component: CommunityIndex,
});

function CommunityIndex() {
  const { user } = Route.useRouteContext();
  const [subject, setSubject] = useState("");
  const { data: threads, isLoading } = useQuery(threadsQueryOptions(subject));

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Communauté</h1>
          <p className="mt-1 text-muted-foreground">Pose tes questions, aide les autres.</p>
        </div>
        <NewThreadDialog authorId={user.id} />
      </div>

      <div className="relative mt-6 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Filtrer par matière…" className="pl-9" />
      </div>

      <div className="mt-6 space-y-2">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)
        ) : threads && threads.length > 0 ? (
          <StaggerGroup className="space-y-2">
            {threads.map((t) => (
              <StaggerItem key={t.id}>
                <Link to="/community/$threadId" params={{ threadId: t.id }}>
                  <Card className="hover-lift flex items-center gap-3 p-4">
                    <Avatar className="size-9 shrink-0">
                      <AvatarImage src={t.author?.avatar_url ?? undefined} />
                      <AvatarFallback>{(t.author?.full_name ?? "?").charAt(0)}</AvatarFallback>
                    </Avatar>
                    <div className="min-w-0 flex-1">
                      <h2 className="truncate text-sm font-semibold">{t.title}</h2>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <Badge variant="secondary">{t.subject}</Badge>
                        <span>{t.level}</span>
                        <span>· {t.author?.full_name ?? "Anonyme"}</span>
                      </div>
                    </div>
                    <div className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                      <MessageSquare className="size-3.5" /> {t.posts_count}
                    </div>
                  </Card>
                </Link>
              </StaggerItem>
            ))}
          </StaggerGroup>
        ) : (
          <p className="text-sm text-muted-foreground">Aucune discussion pour le moment.</p>
        )}
      </div>
    </div>
  );
}

function NewThreadDialog({ authorId }: { authorId: string }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [subject, setSubject] = useState("");
  const [level, setLevel] = useState("");
  const navigate = Route.useNavigate();
  const create = useCreateThread(authorId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const { id } = await create.mutateAsync({ title, body, subject, level });
      setOpen(false);
      navigate({ to: "/community/$threadId", params: { threadId: id } });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de créer cette discussion.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="size-4" /> Nouvelle discussion
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle discussion</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="title">Titre</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="subject">Matière</Label>
              <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="level">Niveau</Label>
              <Input id="level" value={level} onChange={(e) => setLevel(e.target.value)} placeholder="3AS Sciences" required />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="body">Message</Label>
            <Textarea id="body" value={body} onChange={(e) => setBody(e.target.value)} rows={5} required />
          </div>
          <Button type="submit" disabled={create.isPending} className="w-full">
            {create.isPending ? "Publication…" : "Publier"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
