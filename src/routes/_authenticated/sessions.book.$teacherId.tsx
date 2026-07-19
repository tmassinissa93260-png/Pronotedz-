import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Clock, User, Users, CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { teacherProfileQueryOptions, openSlotsQueryOptions, myBookedSessionIdsQueryOptions, type OpenSlot } from "@/lib/queries/teachers";
import { useBookSession } from "@/hooks/use-session-actions";
import { useStartCheckout } from "@/hooks/use-payment-actions";

export const Route = createFileRoute("/_authenticated/sessions/book/$teacherId")({
  component: BookTeacher,
});

function BookTeacher() {
  const { teacherId } = Route.useParams();
  const { user } = Route.useRouteContext();
  const navigate = useNavigate();
  const { data: teacher } = useQuery(teacherProfileQueryOptions(teacherId));
  const { data: slots, isLoading } = useQuery(openSlotsQueryOptions(teacherId));
  const { data: bookedIds } = useQuery(myBookedSessionIdsQueryOptions(user.id));

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <Link to="/teachers/$teacherId" params={{ teacherId }} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Retour au profil
      </Link>

      <h1 className="mt-3 font-display text-2xl font-bold tracking-tight sm:text-3xl">
        Réserver — {teacher?.profile?.full_name ?? "Professeur"}
      </h1>

      <div className="mt-6 space-y-3">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        ) : slots && slots.length > 0 ? (
          <StaggerGroup className="space-y-3">
            {slots.map((slot) => (
              <StaggerItem key={slot.id}>
                <SlotRow
                  slot={slot}
                  studentId={user.id}
                  mine={bookedIds?.has(slot.id) ?? false}
                  onBooked={() => navigate({ to: "/live/$sessionId", params: { sessionId: slot.id } })}
                />
              </StaggerItem>
            ))}
          </StaggerGroup>
        ) : (
          <Card className="p-8 text-center">
            <p className="text-sm text-muted-foreground">Ce prof n'a pas de créneau publié pour l'instant.</p>
          </Card>
        )}
      </div>
    </div>
  );
}

function SlotRow({
  slot,
  studentId,
  mine,
  onBooked,
}: {
  slot: OpenSlot;
  studentId: string;
  mine: boolean;
  onBooked: () => void;
}) {
  const book = useBookSession(slot.id, studentId);
  const checkout = useStartCheckout();
  const full = slot.booked >= slot.max_students;
  const isGroup = slot.session_type === "group";

  async function handleBook() {
    try {
      if (slot.price_per_student > 0) {
        const { checkoutUrl } = await checkout.mutateAsync({ itemType: "session", itemId: slot.id });
        window.location.href = checkoutUrl;
        return;
      }
      const res = await book.mutateAsync();
      if (!res.alreadyBooked) toast.success("Réservation confirmée !");
      onBooked();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de réserver ce créneau.");
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div className="text-xs uppercase tracking-wider text-muted-foreground">{slot.title ?? slot.subject}</div>
        <div className="mt-1 flex flex-wrap items-center gap-3 text-sm">
          <span className="inline-flex items-center gap-1 font-medium">
            <Clock className="size-3.5" />
            {new Date(slot.scheduled_at).toLocaleString("fr-DZ", { dateStyle: "medium", timeStyle: "short" })}
          </span>
          <span className="text-muted-foreground">{slot.duration_min} min</span>
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            {isGroup ? <Users className="size-3.5" /> : <User className="size-3.5" />}
            {isGroup ? `Groupe (${slot.booked}/${slot.max_students})` : "Solo"}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <div className="font-display text-lg font-bold text-primary">
            {Number(slot.price_per_student).toLocaleString()} DZD
          </div>
        </div>
        {mine ? (
          <Button asChild variant="secondary">
            <Link to="/live/$sessionId" params={{ sessionId: slot.id }}>
              <CheckCircle2 className="size-4" /> Réservé
            </Link>
          </Button>
        ) : (
          <Button onClick={handleBook} disabled={full || book.isPending || checkout.isPending}>
            {book.isPending || checkout.isPending ? "…" : full ? "Complet" : slot.price_per_student > 0 ? "Payer et réserver" : "Réserver"}
          </Button>
        )}
      </div>
    </Card>
  );
}
