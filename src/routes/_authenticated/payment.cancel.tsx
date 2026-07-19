import { createFileRoute, Link } from "@tanstack/react-router";
import { XCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Search = { payment_id?: string };

export const Route = createFileRoute("/_authenticated/payment/cancel")({
  validateSearch: (s: Record<string, unknown>): Search => ({
    payment_id: typeof s.payment_id === "string" ? s.payment_id : undefined,
  }),
  component: PaymentCancel,
});

function PaymentCancel() {
  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center sm:px-6">
      <Card className="p-8">
        <XCircle className="mx-auto size-10 text-muted-foreground" />
        <h1 className="mt-4 font-display text-xl font-bold">Paiement annulé</h1>
        <p className="mt-2 text-sm text-muted-foreground">Aucun montant n'a été débité. Tu peux réessayer à tout moment.</p>
        <Button asChild variant="outline" className="mt-5">
          <Link to="/dashboard">Retour au tableau de bord</Link>
        </Button>
      </Card>
    </div>
  );
}
