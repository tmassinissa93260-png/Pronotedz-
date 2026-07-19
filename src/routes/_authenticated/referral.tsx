import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy, Gift, Users, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { FadeIn } from "@/components/motion/fade-in";
import { referralStatusQueryOptions } from "@/lib/queries/referral";

export const Route = createFileRoute("/_authenticated/referral")({
  component: ReferralPage,
});

function ReferralPage() {
  const { user } = Route.useRouteContext();
  const { data, isLoading } = useQuery(referralStatusQueryOptions(user.id));

  const link = data?.referralCode ? `${window.location.origin}/auth?mode=signup&ref=${data.referralCode}` : null;

  function copyLink() {
    if (!link) return;
    navigator.clipboard.writeText(link);
    toast.success("Lien copié !");
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-xl px-4 py-8 sm:px-6">
        <Skeleton className="h-9 w-64" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Parrainage</h1>
      <p className="mt-1 text-muted-foreground">Invite 3 amis, débloque 7 jours de fonctionnalités premium.</p>

      <FadeIn>
        <Card className="mt-6 bg-hero p-6 text-center">
          <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-primary/12 text-primary">
            <Gift className="size-6" />
          </div>
          <p className="mt-3 font-mono text-2xl font-bold tracking-widest">{data?.referralCode ?? "—"}</p>
          <Button className="mt-4" onClick={copyLink} disabled={!link}>
            <Copy className="size-4" /> Copier mon lien d'invitation
          </Button>
          {data?.perkActive && (
            <Badge className="mt-4">
              <Sparkles className="size-3" /> Premium actif jusqu'au{" "}
              {new Date(data.perkUnlockedUntil!).toLocaleDateString("fr-DZ")}
            </Badge>
          )}
        </Card>

        <div className="mt-4 grid grid-cols-2 gap-4">
          <Card className="p-5 text-center">
            <div className="font-display text-2xl font-bold text-primary">{data?.acceptedCount ?? 0}</div>
            <p className="mt-1 text-xs text-muted-foreground">Amis inscrits</p>
          </Card>
          <Card className="p-5 text-center">
            <div className="font-display text-2xl font-bold text-accent">{data?.rewardedCount ?? 0}</div>
            <p className="mt-1 text-xs text-muted-foreground">Récompenses débloquées</p>
          </Card>
        </div>

        {data && data.referrals.length > 0 && (
          <Card className="mt-4 p-5">
            <h2 className="inline-flex items-center gap-1.5 font-display text-sm font-semibold">
              <Users className="size-4" /> Historique
            </h2>
            <div className="mt-3 space-y-2">
              {data.referrals.map((r) => (
                <div key={r.id} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{new Date(r.created_at).toLocaleDateString("fr-DZ")}</span>
                  <Badge variant={r.status === "rewarded" ? "default" : "secondary"}>{r.status}</Badge>
                </div>
              ))}
            </div>
          </Card>
        )}
      </FadeIn>
    </div>
  );
}
