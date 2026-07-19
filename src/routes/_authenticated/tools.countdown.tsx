import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { examCountdownsQueryOptions } from "@/lib/queries/tools";

export const Route = createFileRoute("/_authenticated/tools/countdown")({
  component: CountdownPage,
});

function useNow() {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

function CountdownPage() {
  const { data: countdowns, isLoading } = useQuery(examCountdownsQueryOptions());
  const now = useNow();

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-bold tracking-tight">Compte à rebours</h1>
      <p className="mt-1 text-muted-foreground">Le temps qu'il te reste avant les examens.</p>

      <div className="mt-8 space-y-4">
        {isLoading ? (
          <Skeleton className="h-32" />
        ) : countdowns && countdowns.length > 0 ? (
          <StaggerGroup className="space-y-4">
            {countdowns.map((c) => {
              const target = new Date(c.exam_date).getTime();
              const diff = Math.max(0, target - now);
              const days = Math.floor(diff / 86400000);
              const hours = Math.floor((diff % 86400000) / 3600000);
              const minutes = Math.floor((diff % 3600000) / 60000);
              const seconds = Math.floor((diff % 60000) / 1000);
              return (
                <StaggerItem key={c.id}>
                  <Card className="bg-hero p-6 text-center">
                    <div className="font-display text-lg font-bold uppercase tracking-wide">
                      {c.exam} {c.year}
                    </div>
                    <div className="mt-4 grid grid-cols-4 gap-3">
                      {[
                        { label: "Jours", value: days },
                        { label: "Heures", value: hours },
                        { label: "Minutes", value: minutes },
                        { label: "Secondes", value: seconds },
                      ].map((unit) => (
                        <div key={unit.label}>
                          <div className="font-mono text-3xl font-bold text-primary tabular-nums">
                            {String(unit.value).padStart(2, "0")}
                          </div>
                          <div className="mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                            {unit.label}
                          </div>
                        </div>
                      ))}
                    </div>
                    <p className="mt-4 text-xs text-muted-foreground">
                      {new Date(c.exam_date).toLocaleDateString("fr-DZ", { dateStyle: "full" })}
                    </p>
                  </Card>
                </StaggerItem>
              );
            })}
          </StaggerGroup>
        ) : (
          <p className="text-sm text-muted-foreground">Aucune date d'examen renseignée pour le moment.</p>
        )}
      </div>
    </div>
  );
}
