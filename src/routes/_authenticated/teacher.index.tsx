import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { CalendarClock, Plus, Users, User as UserIcon, Settings2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { useCurrentUser } from "@/hooks/use-current-user";
import { teacherScheduleQueryOptions } from "@/lib/queries/teachers";
import { useCreateSessionSlot } from "@/hooks/use-session-actions";
import { ALL_TEACHABLE_LEVELS } from "@/lib/curriculum/school-levels";
import type { Database } from "@/lib/supabase/types";

type SchoolLevel = Database["public"]["Enums"]["school_level"];

export const Route = createFileRoute("/_authenticated/teacher/")({
  component: TeacherSpace,
});

function TeacherSpace() {
  const { user } = Route.useRouteContext();
  const { data: userData, isLoading: userLoading } = useCurrentUser();
  const isTeacher = userData?.roles.includes("teacher") ?? false;

  if (userLoading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <Skeleton className="h-9 w-64" />
      </div>
    );
  }

  if (!isTeacher) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
        <p className="text-sm text-muted-foreground">Cette page est réservée aux profs.</p>
      </div>
    );
  }

  return <TeacherSchedule teacherId={user.id} />;
}

function TeacherSchedule({ teacherId }: { teacherId: string }) {
  const { data: sessions, isLoading } = useQuery(teacherScheduleQueryOptions(teacherId));

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Espace prof</h1>
          <p className="mt-1 text-muted-foreground">Tes sessions et réservations.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link to="/teacher/availability">
              <Settings2 className="size-4" /> Disponibilités
            </Link>
          </Button>
          <CreateSlotDialog teacherId={teacherId} />
        </div>
      </div>

      <div className="mt-8 space-y-3">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        ) : sessions && sessions.length > 0 ? (
          <StaggerGroup className="space-y-3">
            {sessions.map((s) => (
              <StaggerItem key={s.id}>
                <Link to="/live/$sessionId" params={{ sessionId: s.id }}>
                  <Card className="hover-lift p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-xs uppercase tracking-wider text-muted-foreground">{s.title ?? s.subject}</div>
                        <div className="mt-1 flex items-center gap-2 text-sm font-medium">
                          <CalendarClock className="size-3.5 text-muted-foreground" />
                          {new Date(s.scheduled_at).toLocaleString("fr-DZ", { dateStyle: "medium", timeStyle: "short" })}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {s.session_type === "group" ? <Users className="size-4 text-muted-foreground" /> : <UserIcon className="size-4 text-muted-foreground" />}
                        <span className="text-sm text-muted-foreground">{s.bookings.length}/{s.max_students}</span>
                      </div>
                    </div>
                    {s.bookings.length > 0 && (
                      <div className="mt-3 flex -space-x-2">
                        {s.bookings.map((b) => (
                          <Avatar key={b.id} className="size-7 border-2 border-card">
                            <AvatarImage src={b.student?.avatar_url ?? undefined} />
                            <AvatarFallback className="text-[10px]">{(b.student?.full_name ?? "?").charAt(0)}</AvatarFallback>
                          </Avatar>
                        ))}
                      </div>
                    )}
                  </Card>
                </Link>
              </StaggerItem>
            ))}
          </StaggerGroup>
        ) : (
          <Card className="p-8 text-center">
            <p className="text-sm text-muted-foreground">Aucune session à venir. Crée un créneau pour commencer.</p>
          </Card>
        )}
      </div>
    </div>
  );
}

function CreateSlotDialog({ teacherId }: { teacherId: string }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [level, setLevel] = useState<SchoolLevel>("lycee_3_sciences");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [duration, setDuration] = useState(45);
  const [sessionType, setSessionType] = useState<"solo" | "group">("solo");
  const [maxStudents, setMaxStudents] = useState(1);
  const [price, setPrice] = useState(1500);
  const create = useCreateSessionSlot(teacherId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!date || !time || !subject) {
      toast.error("Renseigne au moins la matière, la date et l'heure.");
      return;
    }
    try {
      await create.mutateAsync({
        title: title || null,
        subject,
        level,
        scheduledAt: new Date(`${date}T${time}`),
        durationMin: duration,
        sessionType,
        maxStudents,
        pricePerStudent: price,
      });
      toast.success("Créneau publié.");
      setOpen(false);
      setSubject("");
      setTitle("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de créer ce créneau.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="size-4" /> Créer un créneau
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouveau créneau</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="subject">Matière</Label>
            <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="title">
              Titre <span className="font-normal text-muted-foreground">(optionnel)</span>
            </Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Niveau</Label>
            <Select value={level} onValueChange={(v) => setLevel(v as SchoolLevel)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ALL_TEACHABLE_LEVELS.map((l) => (
                  <SelectItem key={l.schoolLevel} value={l.schoolLevel}>
                    {l.label_fr}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="date">Date</Label>
              <Input id="date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="time">Heure</Label>
              <Input id="time" type="time" value={time} onChange={(e) => setTime(e.target.value)} required />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="duration">Durée (min)</Label>
              <Input id="duration" type="number" min={15} max={240} value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="price">Prix / élève (DZD)</Label>
              <Input id="price" type="number" min={0} value={price} onChange={(e) => setPrice(Number(e.target.value))} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Type de session</Label>
            <Select value={sessionType} onValueChange={(v) => setSessionType(v as "solo" | "group")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="solo">Solo (1 élève)</SelectItem>
                <SelectItem value="group">Groupe</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {sessionType === "group" && (
            <div className="space-y-1.5">
              <Label htmlFor="maxStudents">Nombre d'élèves max</Label>
              <Input
                id="maxStudents"
                type="number"
                min={2}
                max={5}
                value={maxStudents}
                onChange={(e) => setMaxStudents(Number(e.target.value))}
              />
            </div>
          )}
          <Button type="submit" disabled={create.isPending} className="w-full">
            {create.isPending ? "Publication…" : "Publier le créneau"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
