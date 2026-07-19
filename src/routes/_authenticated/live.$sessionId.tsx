import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Clock, Video, Ban, CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { FadeIn } from "@/components/motion/fade-in";
import { sessionDetailQueryOptions } from "@/lib/queries/teachers";
import { useJoinLiveRoom } from "@/hooks/use-live-room";

export const Route = createFileRoute("/_authenticated/live/$sessionId")({
  component: LiveSessionRoom,
});

function useCountdown(target: number) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return Math.max(0, target - now);
}

function formatCountdown(ms: number) {
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return h > 0 ? `${h}h ${m}min` : m > 0 ? `${m}min ${s}s` : `${s}s`;
}

function LiveSessionRoom() {
  const { sessionId } = Route.useParams();
  const { user } = Route.useRouteContext();
  const { data, isLoading } = useQuery(sessionDetailQueryOptions(sessionId, user.id));
  const [roomUrl, setRoomUrl] = useState<string | null>(null);
  const joinRoom = useJoinLiveRoom(sessionId);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center sm:px-6">
        <p className="text-sm text-muted-foreground">Session introuvable.</p>
      </div>
    );
  }

  const { session, isTeacher, myBooking } = data;
  const hasAccess = isTeacher || Boolean(myBooking);

  if (!hasAccess) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center sm:px-6">
        <p className="text-sm text-muted-foreground">Tu n'es pas inscrit à cette session.</p>
        <Button asChild variant="outline" className="mt-4">
          <Link to="/teachers">Voir les profs</Link>
        </Button>
      </div>
    );
  }

  if (roomUrl) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col bg-black">
        <div className="flex items-center justify-between bg-background/90 px-4 py-2 backdrop-blur">
          <span className="text-sm font-medium">{session.title ?? session.subject}</span>
          <Button size="sm" variant="ghost" onClick={() => setRoomUrl(null)}>
            Fermer
          </Button>
        </div>
        <iframe
          src={roomUrl}
          allow="camera; microphone; fullscreen; speaker; display-capture; autoplay"
          className="flex-1 border-0"
          title="Session en direct"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Retour
      </Link>

      <FadeIn>
        <Card className="mt-4 p-6 text-center">
          <div className="grid size-14 place-items-center rounded-2xl bg-primary/12 text-primary mx-auto">
            <Video className="size-6" />
          </div>
          <h1 className="mt-4 font-display text-xl font-bold">{session.title ?? session.subject}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {new Date(session.scheduled_at).toLocaleString("fr-DZ", { dateStyle: "full", timeStyle: "short" })} ·{" "}
            {session.duration_min} min
          </p>

          <div className="mt-6">
            {session.status === "cancelled" ? (
              <p className="inline-flex items-center gap-2 text-sm font-medium text-destructive">
                <Ban className="size-4" /> Cette session a été annulée.
              </p>
            ) : session.status === "completed" ? (
              <div>
                <p className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <CheckCircle2 className="size-4" /> Cette session est terminée.
                </p>
                {session.recording_url && (
                  <Button asChild variant="outline" className="mt-3">
                    <a href={session.recording_url} target="_blank" rel="noopener noreferrer">
                      Voir l'enregistrement
                    </a>
                  </Button>
                )}
              </div>
            ) : (
              <JoinPanel scheduledAt={session.scheduled_at} joinRoom={joinRoom} onJoined={setRoomUrl} />
            )}
          </div>
        </Card>
      </FadeIn>
    </div>
  );
}

function JoinPanel({
  scheduledAt,
  joinRoom,
  onJoined,
}: {
  scheduledAt: string;
  joinRoom: ReturnType<typeof useJoinLiveRoom>;
  onJoined: (url: string) => void;
}) {
  const openAt = new Date(scheduledAt).getTime() - 15 * 60 * 1000;
  const remaining = useCountdown(openAt);
  const canJoin = remaining <= 0;

  async function handleJoin() {
    try {
      const url = await joinRoom.mutateAsync();
      onJoined(url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de rejoindre la session.");
    }
  }

  if (!canJoin) {
    return (
      <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
        <Clock className="size-4" /> La salle ouvre dans {formatCountdown(remaining)}
      </p>
    );
  }

  return (
    <Button size="lg" onClick={handleJoin} disabled={joinRoom.isPending}>
      <Video className="size-4" /> {joinRoom.isPending ? "Connexion…" : "Rejoindre la session"}
    </Button>
  );
}
