import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Heart, Flag, Send } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { cn } from "@/lib/utils";
import { threadQueryOptions, postsQueryOptions, myLikesQueryOptions } from "@/lib/queries/community";
import { useCreatePost, useToggleLike, useReportContent } from "@/hooks/use-community-actions";

export const Route = createFileRoute("/_authenticated/community/$threadId")({
  component: ThreadDetail,
});

function ThreadDetail() {
  const { threadId } = Route.useParams();
  const { user } = Route.useRouteContext();
  const { data: thread, isLoading: threadLoading } = useQuery(threadQueryOptions(threadId));
  const { data: posts, isLoading: postsLoading } = useQuery(postsQueryOptions(threadId));
  const { data: myLikes } = useQuery(myLikesQueryOptions((posts ?? []).map((p) => p.id), user.id));
  const createPost = useCreatePost(threadId, user.id);
  const toggleLike = useToggleLike(threadId, user.id);
  const [reply, setReply] = useState("");

  if (threadLoading) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
        <Skeleton className="h-9 w-64" />
      </div>
    );
  }
  if (!thread) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center sm:px-6">
        <p className="text-sm text-muted-foreground">Discussion introuvable.</p>
      </div>
    );
  }

  async function handleReply(e: React.FormEvent) {
    e.preventDefault();
    if (!reply.trim()) return;
    const text = reply;
    setReply("");
    try {
      await createPost.mutateAsync(text);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Message non envoyé.");
      setReply(text);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <BreadcrumbNav items={[{ label: "Communauté", to: "/community" }, { label: thread.title }]} />

      <Card className="mt-2 p-5">
        <div className="flex items-start gap-3">
          <Avatar className="size-9 shrink-0">
            <AvatarImage src={thread.author?.avatar_url ?? undefined} />
            <AvatarFallback>{(thread.author?.full_name ?? "?").charAt(0)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-lg font-bold">{thread.title}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="secondary">{thread.subject}</Badge>
              <span>{thread.level}</span>
              <span>· {thread.author?.full_name ?? "Anonyme"}</span>
            </div>
            <p className="mt-3 whitespace-pre-wrap text-sm">{thread.body}</p>
          </div>
          <ReportButton reporterId={user.id} targetType="thread" targetId={thread.id} />
        </div>
      </Card>

      <div className="mt-4 space-y-3">
        {postsLoading ? (
          <Skeleton className="h-16" />
        ) : (
          (posts ?? []).map((p) => (
            <Card key={p.id} className="p-4">
              <div className="flex items-start gap-3">
                <Avatar className="size-8 shrink-0">
                  <AvatarImage src={p.author?.avatar_url ?? undefined} />
                  <AvatarFallback className="text-xs">{(p.author?.full_name ?? "?").charAt(0)}</AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-muted-foreground">{p.author?.full_name ?? "Anonyme"}</div>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{p.body}</p>
                  <div className="mt-2 flex items-center gap-3">
                    <button
                      onClick={() => toggleLike.mutate({ postId: p.id, currentlyLiked: myLikes?.has(p.id) ?? false })}
                      className={cn(
                        "inline-flex items-center gap-1 text-xs transition-colors",
                        myLikes?.has(p.id) ? "text-destructive" : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <Heart className={cn("size-3.5", myLikes?.has(p.id) && "fill-current")} /> {p.likes_count}
                    </button>
                    <ReportButton reporterId={user.id} targetType="post" targetId={p.id} compact />
                  </div>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>

      <form onSubmit={handleReply} className="mt-4 flex gap-2">
        <Input value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Répondre…" />
        <Button type="submit" size="icon" disabled={createPost.isPending}>
          <Send className="size-4" />
        </Button>
      </form>
    </div>
  );
}

function ReportButton({
  reporterId,
  targetType,
  targetId,
  compact,
}: {
  reporterId: string;
  targetType: "thread" | "post";
  targetId: string;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const report = useReportContent(reporterId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await report.mutateAsync({ targetType, targetId, reason });
      toast.success("Signalement envoyé.");
      setOpen(false);
      setReason("");
    } catch {
      toast.error("Impossible d'envoyer le signalement.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button className={cn("inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive", compact ? "" : "shrink-0")}>
          <Flag className="size-3.5" /> {!compact && "Signaler"}
        </button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Signaler ce contenu</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Pourquoi signales-tu ce contenu ?" rows={3} required />
          <Button type="submit" disabled={report.isPending} className="w-full">
            Envoyer le signalement
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
