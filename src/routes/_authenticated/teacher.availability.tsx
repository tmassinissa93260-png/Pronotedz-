import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { teacherAvailabilityQueryOptions } from "@/lib/queries/teachers";
import { useUpsertAvailability, useDeleteAvailability } from "@/hooks/use-session-actions";

export const Route = createFileRoute("/_authenticated/teacher/availability")({
  component: AvailabilityPage,
});

const DAYS = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];

function AvailabilityPage() {
  const { user } = Route.useRouteContext();
  const { data: availability, isLoading } = useQuery(teacherAvailabilityQueryOptions(user.id));
  const upsert = useUpsertAvailability(user.id);
  const remove = useDeleteAvailability(user.id);

  const [dayOfWeek, setDayOfWeek] = useState("1");
  const [startTime, setStartTime] = useState("14:00");
  const [endTime, setEndTime] = useState("18:00");

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    try {
      await upsert.mutateAsync({ dayOfWeek: Number(dayOfWeek), startTime, endTime, recurring: true });
      toast.success("Créneau de disponibilité ajouté.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible d'ajouter ce créneau.");
    }
  }

  async function handleRemove(id: string) {
    try {
      await remove.mutateAsync(id);
    } catch {
      toast.error("Impossible de supprimer ce créneau.");
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <Link to="/teacher" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Espace prof
      </Link>
      <h1 className="mt-3 font-display text-2xl font-bold tracking-tight sm:text-3xl">Disponibilités habituelles</h1>
      <p className="mt-1 text-muted-foreground">
        Un repère indicatif affiché sur ton profil — les élèves réservent toujours un créneau que tu publies explicitement.
      </p>

      <Card className="mt-6 p-5">
        <form onSubmit={handleAdd} className="grid grid-cols-1 gap-3 sm:grid-cols-4 sm:items-end">
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Jour</Label>
            <Select value={dayOfWeek} onValueChange={setDayOfWeek}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DAYS.map((d, i) => (
                  <SelectItem key={i} value={String(i)}>
                    {d}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="start">Début</Label>
            <Input id="start" type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="end">Fin</Label>
            <Input id="end" type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
          </div>
          <Button type="submit" disabled={upsert.isPending} className="sm:col-span-4">
            <Plus className="size-4" /> Ajouter
          </Button>
        </form>
      </Card>

      <div className="mt-6 space-y-2">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14" />)
        ) : availability && availability.length > 0 ? (
          availability.map((slot) => (
            <Card key={slot.id} className="flex items-center justify-between p-3.5">
              <span className="text-sm">
                <span className="font-medium">{DAYS[slot.day_of_week]}</span>
                <span className="text-muted-foreground"> · {slot.start_time.slice(0, 5)}–{slot.end_time.slice(0, 5)}</span>
              </span>
              <Button size="icon" variant="ghost" onClick={() => handleRemove(slot.id)} aria-label="Supprimer">
                <Trash2 className="size-4 text-destructive" />
              </Button>
            </Card>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">Aucune disponibilité renseignée.</p>
        )}
      </div>
    </div>
  );
}
