import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Send, FileText, CalendarDays, Upload, Trash2, Copy, LogOut } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
} from "@/lib/queries/groups";
import {
  useSendGroupMessage,
  useLeaveGroup,
  useUploadGroupResource,
  useDeleteGroupResource,
  useCreateGroupEvent,
  useDeleteGroupEvent,
} from "@/hooks/use-group-actions";
import { useGroupMessagesRealtime } from "@/hooks/use-group-messages-realtime";
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
