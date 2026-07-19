import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Send, FileText, CalendarDays, Upload, Trash2, Copy, LogOut, Timer, Coffee, AlertTriangle, Plus, CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import {
  groupQueryOptions,
  groupMembersQueryOptions,
  groupMessagesQueryOptions,
  groupResourcesQueryOptions,
  groupEventsQueryOptions,
  groupPomodoroQueryOptions,
  groupExamAlertsQueryOptions,
  type GroupExamAlert,
} from "@/lib/queries/groups";
import {
  useSendGroupMessage,
  useLeaveGroup,
  useUploadGroupResource,
  useDeleteGroupResource,
  useCreateGroupEvent,
  useDeleteGroupEvent,
  useStartPomodoro,
  useCreateGroupExamAlert,
  useDeleteGroupExamAlert,
} from "@/hooks/use-group-actions";
import { useGroupMessagesRealtime } from "@/hooks/use-group-messages-realtime";
import { useGroupPomodoroRealtime } from "@/hooks/use-group-pomodoro-realtime";
import { supabase } from "@/lib/supabase/client";

export const Route = createFileRoute("/_authenticated/groups/$groupId")({
  component: GroupDetail,
});

function GroupDetail() {
  const { groupId } = Route.useParams();
  const { user } = Route.useRouteContext();
  const { data: group, isLoading } = useQuery(groupQueryOptions(groupId));

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <Skeleton className="h-9 w-64" />
      </div>
    );
  }
  if (!group) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6">
        <p className="text-sm text-muted-foreground">Groupe introuvable — ou tu n'en fais pas partie.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <BreadcrumbNav items={[{ label: "Groupes d'étude", to: "/groups" }, { label: group.name }]} />
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">{group.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{group.subject} · {group.level}</p>
        </div>
        <LeaveGroupButton groupId={groupId} userId={user.id} isOwner={group.owner_id === user.id} />
      </div>
      {group.description && <p className="mt-3 text-sm text-muted-foreground">{group.description}</p>}
      <div className="mt-2 inline-flex items-center gap-2 text-xs text-muted-foreground">
        Code d'invitation :
        <button
          onClick={() => {
            navigator.clipboard.writeText(group.invite_code);
            toast.success("Code copié.");
          }}
          className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-0.5 font-mono font-medium text-foreground"
        >
          {group.invite_code} <Copy className="size-3" />
        </button>
      </div>

      <Tabs defaultValue="chat" className="mt-6">
        <TabsList>
          <TabsTrigger value="chat">Discussion</TabsTrigger>
          <TabsTrigger value="members">Membres</TabsTrigger>
          <TabsTrigger value="resources">Ressources</TabsTrigger>
          <TabsTrigger value="events">Événements</TabsTrigger>
          <TabsTrigger value="pomodoro">Pomodoro</TabsTrigger>
          <TabsTrigger value="exams">Examens</TabsTrigger>
        </TabsList>
        <TabsContent value="chat">
          <ChatPanel groupId={groupId} userId={user.id} />
        </TabsContent>
        <TabsContent value="members">
          <MembersPanel groupId={groupId} />
        </TabsContent>
        <TabsContent value="resources">
          <ResourcesPanel groupId={groupId} userId={user.id} />
        </TabsContent>
        <TabsContent value="events">
          <EventsPanel groupId={groupId} userId={user.id} />
        </TabsContent>
        <TabsContent value="pomodoro">
          <PomodoroPanel groupId={groupId} userId={user.id} />
        </TabsContent>
        <TabsContent value="exams">
          <ExamAlertsPanel groupId={groupId} userId={user.id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function LeaveGroupButton({ groupId, userId, isOwner }: { groupId: string; userId: string; isOwner: boolean }) {
  const navigate = Route.useNavigate();
  const leave = useLeaveGroup(userId);
  if (isOwner) return null;
  return (
    <Button
      variant="ghost"
      size="sm"
      className="text-muted-foreground"
      onClick={async () => {
        await leave.mutateAsync(groupId);
        toast.success("Tu as quitté le groupe.");
        navigate({ to: "/groups" });
      }}
    >
      <LogOut className="size-4" /> Quitter
    </Button>
  );
}

function ChatPanel({ groupId, userId }: { groupId: string; userId: string }) {
  useGroupMessagesRealtime(groupId);
  const { data: messages, isLoading } = useQuery(groupMessagesQueryOptions(groupId));
  const send = useSendGroupMessage(groupId, userId);
  const [body, setBody] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages?.length]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    const text = body;
    setBody("");
    try {
      await send.mutateAsync(text);
    } catch {
      toast.error("Message non envoyé.");
      setBody(text);
    }
  }

  return (
    <Card className="flex h-[28rem] flex-col p-0">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {isLoading ? (
          <Skeleton className="h-10 w-2/3" />
        ) : messages && messages.length > 0 ? (
          messages.map((m) => (
            <div key={m.id} className={m.author_id === userId ? "flex justify-end" : "flex justify-start"}>
              <div className={`max-w-[75%] rounded-2xl px-3.5 py-2 text-sm ${m.author_id === userId ? "bg-primary text-primary-foreground" : "bg-secondary"}`}>
                {m.author_id !== userId && <div className="text-xs font-semibold opacity-70">{m.author?.full_name ?? "Membre"}</div>}
                <div className="whitespace-pre-wrap">{m.body}</div>
              </div>
            </div>
          ))
        ) : (
          <p className="text-center text-sm text-muted-foreground">Aucun message. Lance la discussion !</p>
        )}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={handleSend} className="flex gap-2 border-t border-border p-3">
        <Input value={body} onChange={(e) => setBody(e.target.value)} placeholder="Écris un message…" />
        <Button type="submit" size="icon" disabled={send.isPending}>
          <Send className="size-4" />
        </Button>
      </form>
    </Card>
  );
}

function MembersPanel({ groupId }: { groupId: string }) {
  const { data: members, isLoading } = useQuery(groupMembersQueryOptions(groupId));
  if (isLoading) return <Skeleton className="h-24" />;
  return (
    <div className="space-y-2">
      {(members ?? []).map((m) => (
        <Card key={m.id} className="flex items-center gap-3 p-3">
          <Avatar className="size-8">
            <AvatarImage src={m.profile?.avatar_url ?? undefined} />
            <AvatarFallback>{(m.profile?.full_name ?? "?").charAt(0)}</AvatarFallback>
          </Avatar>
          <span className="flex-1 text-sm font-medium">{m.profile?.full_name ?? "Membre"}</span>
          {m.role === "owner" && <span className="text-xs text-muted-foreground">Organisateur</span>}
        </Card>
      ))}
    </div>
  );
}

function ResourcesPanel({ groupId, userId }: { groupId: string; userId: string }) {
  const { data: resources, isLoading } = useQuery(groupResourcesQueryOptions(groupId));
  const upload = useUploadGroupResource(groupId, userId);
  const del = useDeleteGroupResource(groupId);
  const [file, setFile] = useState<File | null>(null);

  async function handleUpload() {
    if (!file) return;
    try {
      await upload.mutateAsync({ file, title: file.name });
      setFile(null);
      toast.success("Ressource ajoutée.");
    } catch {
      toast.error("Échec de l'envoi.");
    }
  }

  async function openResource(path: string) {
    const { data, error } = await supabase.storage.from("group-resources").createSignedUrl(path, 3600);
    if (error) return toast.error("Impossible d'ouvrir ce fichier.");
    window.open(data.signedUrl, "_blank", "noopener");
  }

  return (
    <div className="space-y-3">
      <Card className="flex items-center gap-2 p-3">
        <Input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-xs" />
        <Button size="sm" onClick={handleUpload} disabled={!file || upload.isPending}>
          <Upload className="size-4" /> Envoyer
        </Button>
      </Card>
      {isLoading ? (
        <Skeleton className="h-16" />
      ) : resources && resources.length > 0 ? (
        resources.map((r) => (
          <Card key={r.id} className="flex items-center justify-between p-3.5">
            <button onClick={() => openResource(r.storage_path)} className="flex items-center gap-2 text-sm hover:text-primary">
              <FileText className="size-4" /> {r.title}
            </button>
            {r.uploader_id === userId && (
              <Button size="icon" variant="ghost" onClick={() => del.mutate({ id: r.id, path: r.storage_path })}>
                <Trash2 className="size-4 text-destructive" />
              </Button>
            )}
          </Card>
        ))
      ) : (
        <p className="text-sm text-muted-foreground">Aucune ressource partagée.</p>
      )}
    </div>
  );
}

function EventsPanel({ groupId, userId }: { groupId: string; userId: string }) {
  const { data: events, isLoading } = useQuery(groupEventsQueryOptions(groupId));
  const create = useCreateGroupEvent(groupId, userId);
  const del = useDeleteGroupEvent(groupId);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync({ title, description: null, eventAt: new Date(`${date}T${time || "00:00"}`) });
      toast.success("Événement ajouté.");
      setOpen(false);
      setTitle("");
    } catch {
      toast.error("Impossible de créer cet événement.");
    }
  }

  return (
    <div className="space-y-3">
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button size="sm">
            <CalendarDays className="size-4" /> Ajouter un événement
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouvel événement</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="etitle">Titre</Label>
              <Input id="etitle" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edate">Date</Label>
                <Input id="edate" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="etime">Heure</Label>
                <Input id="etime" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
              </div>
            </div>
            <Button type="submit" disabled={create.isPending} className="w-full">
              Ajouter
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      {isLoading ? (
        <Skeleton className="h-16" />
      ) : events && events.length > 0 ? (
        events.map((ev) => (
          <Card key={ev.id} className="flex items-center justify-between p-3.5">
            <div>
              <div className="text-sm font-medium">{ev.title}</div>
              <div className="text-xs text-muted-foreground">
                {new Date(ev.event_at).toLocaleString("fr-DZ", { dateStyle: "medium", timeStyle: "short" })}
              </div>
            </div>
            {ev.created_by === userId && (
              <Button size="icon" variant="ghost" onClick={() => del.mutate(ev.id)}>
                <Trash2 className="size-4 text-destructive" />
              </Button>
            )}
          </Card>
        ))
      ) : (
        <p className="text-sm text-muted-foreground">Aucun événement prévu.</p>
      )}
    </div>
  );
}

const PHASE_LABEL: Record<string, string> = { focus: "Focus", break: "Pause" };
const PHASE_DURATION: Record<string, number> = { focus: 25, break: 5 };

function useCountdown(endsAt: string | undefined) {
  const [remainingMs, setRemainingMs] = useState(() => (endsAt ? new Date(endsAt).getTime() - Date.now() : 0));
  useEffect(() => {
    if (!endsAt) return;
    const tick = () => setRemainingMs(new Date(endsAt).getTime() - Date.now());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [endsAt]);
  return remainingMs;
}

function PomodoroPanel({ groupId, userId }: { groupId: string; userId: string }) {
  useGroupPomodoroRealtime(groupId);
  const { data: session, isLoading } = useQuery(groupPomodoroQueryOptions(groupId));
  const start = useStartPomodoro(groupId, userId);
  const remainingMs = useCountdown(session?.ends_at);
  const isActive = Boolean(session) && remainingMs > 0;

  const minutes = Math.max(0, Math.floor(remainingMs / 60_000));
  const seconds = Math.max(0, Math.floor((remainingMs % 60_000) / 1000));

  async function handleStart(phase: "focus" | "break") {
    try {
      await start.mutateAsync({ phase, durationMin: PHASE_DURATION[phase] });
    } catch {
      toast.error("Impossible de démarrer la session.");
    }
  }

  if (isLoading) return <Skeleton className="h-48" />;

  return (
    <Card className="flex flex-col items-center gap-4 p-8 text-center">
      {isActive && session ? (
        <>
          <Badge variant={session.phase === "focus" ? "default" : "secondary"} className="text-xs">
            {session.phase === "focus" ? <Timer className="size-3" /> : <Coffee className="size-3" />}
            {PHASE_LABEL[session.phase] ?? session.phase}
          </Badge>
          <div className="font-display text-6xl font-bold tabular-nums tracking-tight">
            {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}
          </div>
          <p className="text-sm text-muted-foreground">Session synchronisée pour tout le groupe.</p>
        </>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">Aucune session en cours. Lance un pomodoro pour tout le groupe.</p>
          <div className="flex gap-2">
            <Button onClick={() => handleStart("focus")} disabled={start.isPending}>
              <Timer className="size-4" /> Focus 25 min
            </Button>
            <Button variant="outline" onClick={() => handleStart("break")} disabled={start.isPending}>
              <Coffee className="size-4" /> Pause 5 min
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}

function ExamAlertsPanel({ groupId, userId }: { groupId: string; userId: string }) {
  const { data: alerts, isLoading } = useQuery(groupExamAlertsQueryOptions(groupId));
  const del = useDeleteGroupExamAlert(groupId);

  return (
    <div className="space-y-3">
      <CreateExamAlertDialog groupId={groupId} />
      {isLoading ? (
        <Skeleton className="h-24" />
      ) : alerts && alerts.length > 0 ? (
        alerts.map((alert) => (
          <ExamAlertCard key={alert.id} alert={alert} canDelete={alert.created_by === userId} onDelete={() => del.mutate(alert.id)} />
        ))
      ) : (
        <p className="text-sm text-muted-foreground">Aucune alerte examen. Crée-en une pour générer un quiz de révision IA.</p>
      )}
    </div>
  );
}

function ExamAlertCard({
  alert,
  canDelete,
  onDelete,
}: {
  alert: GroupExamAlert;
  canDelete: boolean;
  onDelete: () => void;
}) {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const quiz = (alert.quiz as { question: string; options: string[]; correct_index: number; explanation: string }[]) ?? [];
  const checklist = (alert.checklist as string[]) ?? [];
  const daysLeft = Math.ceil((new Date(alert.exam_date).getTime() - Date.now()) / (24 * 60 * 60 * 1000));

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-4 text-accent" />
            <h3 className="text-sm font-semibold">{alert.subject}</h3>
            <Badge variant={daysLeft <= 3 ? "default" : "outline"}>{daysLeft > 0 ? `J-${daysLeft}` : "Aujourd'hui"}</Badge>
          </div>
          {alert.chapters.length > 0 && <p className="mt-1 text-xs text-muted-foreground">{alert.chapters.join(", ")}</p>}
        </div>
        {canDelete && (
          <Button size="icon" variant="ghost" onClick={onDelete}>
            <Trash2 className="size-4 text-destructive" />
          </Button>
        )}
      </div>

      {checklist.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {checklist.map((item, i) => (
            <label key={i} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={Boolean(checked[i])}
                onChange={(e) => setChecked((prev) => ({ ...prev, [i]: e.target.checked }))}
                className="size-4 rounded border-input"
              />
              <span className={checked[i] ? "text-muted-foreground line-through" : ""}>{item}</span>
            </label>
          ))}
        </div>
      )}

      {quiz.length > 0 && (
        <div className="mt-4 space-y-4 border-t border-border pt-4">
          {quiz.map((q, qi) => (
            <div key={qi}>
              <p className="text-sm font-medium">{q.question}</p>
              <div className="mt-1.5 grid gap-1.5">
                {q.options.map((opt, oi) => {
                  const selected = answers[qi] === oi;
                  const revealed = answers[qi] !== undefined;
                  const isCorrect = oi === q.correct_index;
                  return (
                    <button
                      key={oi}
                      onClick={() => setAnswers((prev) => ({ ...prev, [qi]: oi }))}
                      disabled={revealed}
                      className={`rounded-lg border px-3 py-1.5 text-left text-sm transition-colors ${
                        revealed && isCorrect
                          ? "border-primary bg-primary/10"
                          : revealed && selected
                            ? "border-destructive bg-destructive/10"
                            : "border-border hover:bg-secondary"
                      }`}
                    >
                      {opt}
                      {revealed && isCorrect && <CheckCircle2 className="ml-1.5 inline size-3.5 text-primary" />}
                    </button>
                  );
                })}
              </div>
              {answers[qi] !== undefined && <p className="mt-1 text-xs text-muted-foreground">{q.explanation}</p>}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function CreateExamAlertDialog({ groupId }: { groupId: string }) {
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState("");
  const [chapters, setChapters] = useState("");
  const [date, setDate] = useState("");
  const create = useCreateGroupExamAlert(groupId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync({
        groupId,
        subject: subject.trim(),
        chapters: chapters.split(",").map((c) => c.trim()).filter(Boolean),
        examDate: new Date(date),
      });
      toast.success("Alerte examen créée — quiz généré par l'IA.");
      setOpen(false);
      setSubject("");
      setChapters("");
      setDate("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de créer cette alerte.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="size-4" /> Alerte examen + quiz IA
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle alerte examen</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="asubject">Matière</Label>
            <Input id="asubject" value={subject} onChange={(e) => setSubject(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="achapters">Chapitres (séparés par une virgule)</Label>
            <Input id="achapters" value={chapters} onChange={(e) => setChapters(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="adate">Date de l'examen</Label>
            <Input id="adate" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </div>
          <Button type="submit" disabled={create.isPending} className="w-full">
            {create.isPending ? "Génération du quiz…" : "Créer et générer le quiz"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
