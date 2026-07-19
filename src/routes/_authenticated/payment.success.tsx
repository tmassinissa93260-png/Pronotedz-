import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { paymentQueryOptions } from "@/lib/queries/payments";

type Search = { payment_id?: string };

export const Route = createFileRoute("/_authenticated/payment/success")({
  validateSearch: (s: Record<string, unknown>): Search => ({
    payment_id: typeof s.payment_id === "string" ? s.payment_id : undefined,
  }),
  component: PaymentSuccess,
});

function PaymentSuccess() {
  const { payment_id } = Route.useSearch();
  const { data: payment, isLoading } = useQuery(paymentQueryOptions(payment_id));

  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center sm:px-6">
      <Card className="p-8">
        {isLoading || payment?.status === "pending" ? (
          <>
            <Loader2 className="mx-auto size-10 animate-spin text-muted-foreground" />
            <h1 className="mt-4 font-display text-xl font-bold">Confirmation en cours…</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Ton paiement a été reçu par Chargily, on attend la confirmation finale — ça prend quelques secondes.
            </p>
          </>
        ) : payment?.status === "paid" ? (
          <>
            <CheckCircle2 className="mx-auto size-10 text-primary" />
            <h1 className="mt-4 font-display text-xl font-bold">Paiement confirmé !</h1>
            <p className="mt-2 text-sm text-muted-foreground">L'accès a été débloqué. Bonne session !</p>
            {payment.item_type === "course" ? (
              <Button asChild className="mt-5">
                <Link to="/courses/$courseId" params={{ courseId: payment.item_id }}>
                  Accéder au cours
                </Link>
              </Button>
            ) : (
              <Button asChild className="mt-5">
                <Link to="/live/$sessionId" params={{ sessionId: payment.item_id }}>
                  Accéder à la session
                </Link>
              </Button>
            )}
          </>
        ) : (
          <>
            <XCircle className="mx-auto size-10 text-destructive" />
            <h1 className="mt-4 font-display text-xl font-bold">Paiement introuvable</h1>
            <p className="mt-2 text-sm text-muted-foreground">Reviens sur le tableau de bord et réessaie.</p>
            <Button asChild variant="outline" className="mt-5">
              <Link to="/dashboard">Retour au tableau de bord</Link>
            </Button>
          </>
        )}
      </Card>
    </div>
  );
}
