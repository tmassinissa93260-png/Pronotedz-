import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Plus, Check, Trash2, Clock, Bell, BellOff, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { myTasksQueryOptions, type StudentTask } from "@/lib/queries/tasks";
import { myGroupsQueryOptions } from "@/lib/queries/groups";
import { useCreateTask, useMarkTaskDone, useReopenTask, useDeleteTask } from "@/hooks/use-task-actions";

export const Route = createFileRoute("/_authenticated/tasks/")({
  component: TasksPage,
});

function TasksPage() {
  const { user } = Route.useRouteContext();
  const { data: tasks, isLoading } = useQuery(myTasksQueryOptions(user.id));

  const todo = (tasks ?? []).filter((t) => t.status !== "done");
  const done = (tasks ?? []).filter((t) => t.status === "done");

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Mes tâches</h1>
          <p className="mt-1 text-sm text-muted-foreground">Planifie tes révisions et reçois un rappel avant l'échéance.</p>
        </div>
        <CreateTaskDialog studentId={user.id} />
      </div>

      <div className="mt-6">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        ) : todo.length > 0 ? (
          <StaggerGroup className="space-y-3">
            {todo.map((task) => (
              <StaggerItem key={task.id}>
                <TaskCard task={task} studentId={user.id} />
              </StaggerItem>
            ))}
          </StaggerGroup>
        ) : (
          <p className="text-sm text-muted-foreground">Aucune tâche en cours. Ajoute ta première révision !</p>
        )}
      </div>

      {done.length > 0 && (
        <div className="mt-8">
          <h2 className="text-sm font-semibold text-muted-foreground">Terminées</h2>
          <div className="mt-3 space-y-2">
            {done.map((task) => (
              <TaskCard key={task.id} task={task} studentId={user.id} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const DIFFICULTY_LABEL: Record<number, string> = { 1: "Facile", 2: "Abordable", 3: "Moyen", 4: "Difficile", 5: "Très difficile" };

function TaskCard({ task, studentId }: { task: StudentTask; studentId: string }) {
  const markDone = useMarkTaskDone(studentId);
  const reopen = useReopenTask(studentId);
  const del = useDeleteTask(studentId);
  const isDone = task.status === "done";
  const overdue = !isDone && task.due_at && new Date(task.due_at).getTime() < Date.now();

  return (
    <Card className={`p-4 ${isDone ? "opacity-60" : ""}`}>
      <div className="flex items-start gap-3">
        <button
          onClick={async () => {
            try {
              if (isDone) {
                await reopen.mutateAsync(task.id);
              } else {
                await markDone.mutateAsync({ taskId: task.id, actualMinutes: task.estimated_minutes, selfGrade: null });
                toast.success("Tâche terminée — +5 XP");
              }
            } catch {
              toast.error("Action impossible.");
            }
          }}
          className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border transition-colors ${
            isDone ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/40 hover:border-primary"
          }`}
        >
          {isDone && <Check className="size-3" />}
        </button>
        <div className="min-w-0 flex-1">
          <p className={`text-sm font-medium ${isDone ? "line-through" : ""}`}>{task.title}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {task.subject && <Badge variant="secondary">{task.subject}</Badge>}
            {task.difficulty > 0 && <Badge variant="outline">{DIFFICULTY_LABEL[task.difficulty] ?? task.difficulty}</Badge>}
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="size-3" /> {task.estimated_minutes} min
            </span>
            {task.due_at && (
              <span className={`text-xs ${overdue ? "font-medium text-destructive" : "text-muted-foreground"}`}>
                {new Date(task.due_at).toLocaleString("fr-DZ", { dateStyle: "medium", timeStyle: "short" })}
              </span>
            )}
            {task.channels.length > 0 ? (
              <Bell className="size-3 text-primary" />
            ) : (
              <BellOff className="size-3 text-muted-foreground/50" />
            )}
            {task.share_with_group && <Users className="size-3 text-muted-foreground" />}
          </div>
          {task.notes && <p className="mt-1.5 text-xs text-muted-foreground">{task.notes}</p>}
        </div>
        <Button size="icon" variant="ghost" onClick={() => del.mutate(task.id)}>
          <Trash2 className="size-4 text-destructive" />
        </Button>
      </div>
    </Card>
  );
}

function CreateTaskDialog({ studentId }: { studentId: string }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [chapter, setChapter] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [estimatedMinutes, setEstimatedMinutes] = useState(30);
  const [difficulty, setDifficulty] = useState("3");
  const [notes, setNotes] = useState("");
  const [wantsReminder, setWantsReminder] = useState(true);
  const [shareWithGroup, setShareWithGroup] = useState(false);
  const [groupId, setGroupId] = useState<string | null>(null);

  const { data: groups } = useQuery(myGroupsQueryOptions(studentId));
  const create = useCreateTask(studentId);

  function reset() {
    setTitle("");
    setSubject("");
    setChapter("");
    setDate("");
    setTime("");
    setEstimatedMinutes(30);
    setDifficulty("3");
    setNotes("");
    setWantsReminder(true);
    setShareWithGroup(false);
    setGroupId(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync({
        title,
        subject: subject.trim() || null,
        chapter: chapter.trim() || null,
        level: null,
        dueAt: date ? new Date(`${date}T${time || "20:00"}`) : null,
        estimatedMinutes,
        difficulty: Number(difficulty),
        notes: notes.trim() || null,
        groupId,
        shareWithGroup,
        wantsReminder,
      });
      toast.success("Tâche ajoutée.");
      setOpen(false);
      reset();
    } catch {
      toast.error("Impossible de créer cette tâche.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="size-4" /> Nouvelle tâche
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle tâche</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="ttitle">Titre</Label>
            <Input id="ttitle" value={title} onChange={(e) => setTitle(e.target.value)} required placeholder="Réviser les fonctions dérivées" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="tsubject">Matière</Label>
              <Input id="tsubject" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Maths" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tchapter">Chapitre</Label>
              <Input id="tchapter" value={chapter} onChange={(e) => setChapter(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="tdate">Échéance</Label>
              <Input id="tdate" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ttime">Heure</Label>
              <Input id="ttime" type="time" value={time} onChange={(e) => setTime(e.target.value)} disabled={!date} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="tminutes">Durée estimée (min)</Label>
              <Input id="tminutes" type="number" min={5} step={5} value={estimatedMinutes} onChange={(e) => setEstimatedMinutes(Number(e.target.value))} />
            </div>
            <div className="space-y-1.5">
              <Label>Difficulté</Label>
              <Select value={difficulty} onValueChange={setDifficulty}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(DIFFICULTY_LABEL).map(([v, label]) => (
                    <SelectItem key={v} value={v}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="tnotes">Notes (optionnel)</Label>
            <Textarea id="tnotes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
          </div>
          <div className="flex items-center gap-2.5">
            <Switch id="reminder" checked={wantsReminder} onCheckedChange={setWantsReminder} disabled={!date} />
            <Label htmlFor="reminder" className="font-normal">
              Me rappeler avant l'échéance
            </Label>
          </div>
          {groups && groups.length > 0 && (
            <div className="flex items-center gap-2.5">
              <Switch
                id="share"
                checked={shareWithGroup}
                onCheckedChange={(v) => {
                  setShareWithGroup(v);
                  if (v && !groupId) setGroupId(groups[0].id);
                }}
              />
              <Label htmlFor="share" className="font-normal">
                Partager avec mon groupe
              </Label>
            </div>
          )}
          {shareWithGroup && groups && groups.length > 0 && (
            <Select value={groupId ?? undefined} onValueChange={setGroupId}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {groups.map((g) => (
                  <SelectItem key={g.id} value={g.id}>
                    {g.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button type="submit" disabled={create.isPending} className="w-full">
            Ajouter
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
