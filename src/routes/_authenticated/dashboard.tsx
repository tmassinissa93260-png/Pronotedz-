import { createFileRoute, Link } from "@tanstack/react-router";
import { Flame, Zap, CalendarClock, Sparkles, Library, Video, ArrowRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useDashboard } from "@/hooks/use-dashboard";
import { usePingStreakOnce } from "@/hooks/use-gamification";
import { useT } from "@/lib/i18n";

export const Route = createFileRoute("/_authenticated/dashboard")({
  component: Dashboard,
});

function Dashboard() {
  const { user } = Route.useRouteContext();
  const t = useT();
  const { data: userData } = useCurrentUser();
  const { data, isLoading } = useDashboard(user.id);
  usePingStreakOnce(user.id);

  const firstName = userData?.profile?.full_name?.split(" ")[0] || user.email?.split("@")[0] || "";

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
          {t("dashboard.greeting", { name: firstName })}
        </h1>
        <p className="mt-1 text-muted-foreground">{t("dashboard.subGreeting")}</p>
      </div>

      <StaggerGroup className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StaggerItem className="sm:col-span-1">
          <StatCard
            icon={Flame}
            label={t("dashboard.streakCard")}
            value={isLoading ? null : t("dashboard.streakDays", { count: data?.streakDays ?? 0 })}
            accent="amber"
          />
        </StaggerItem>
        <StaggerItem className="sm:col-span-1">
          <StatCard
            icon={Zap}
            label={t("dashboard.xpCard")}
            value={isLoading ? null : t("dashboard.xpPoints", { count: data?.xp ?? 0 })}
            accent="emerald"
          />
        </StaggerItem>

        <StaggerItem className="sm:col-span-2 lg:col-span-2 lg:row-span-2">
          <Card className="hover-lift h-full p-5">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-sm font-semibold">{t("dashboard.upcomingSessions")}</h2>
              <CalendarClock className="size-4 text-muted-foreground" />
            </div>
            <div className="mt-4 space-y-3">
              {isLoading ? (
                <>
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                </>
              ) : data && data.upcomingSessions.length > 0 ? (
                data.upcomingSessions.map((s) => (
                  <div
                    key={s.bookingId}
                    className="flex items-center justify-between rounded-xl border border-border bg-secondary/30 px-3.5 py-3"
                  >
                    <div>
                      <div className="text-sm font-medium">{s.title || s.subject}</div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(s.scheduledAt).toLocaleString("fr-DZ", {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}{" "}
                        · {s.durationMin} min
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="flex flex-col items-center gap-3 py-8 text-center">
                  <p className="text-sm text-muted-foreground">{t("dashboard.noUpcomingSessions")}</p>
                  <Button variant="outline" size="sm" asChild>
                    <Link to="/teachers">{t("dashboard.bookSession")}</Link>
                  </Button>
                </div>
              )}
            </div>
          </Card>
        </StaggerItem>

        <StaggerItem className="sm:col-span-2 lg:col-span-2">
          <Card className="hover-lift h-full p-5">
            <h2 className="font-display text-sm font-semibold">{t("dashboard.quickActions")}</h2>
            <div className="mt-4 grid gap-2.5">
              <QuickAction to="/ai" icon={Sparkles} label={t("dashboard.goToAi")} />
              <QuickAction to="/library" icon={Library} label={t("dashboard.goToLibrary")} />
              <QuickAction to="/teachers" icon={Video} label={t("dashboard.goToTeachers")} />
            </div>
          </Card>
        </StaggerItem>

        <StaggerItem className="sm:col-span-2 lg:col-span-2">
          <Card className="hover-lift h-full bg-hero p-5">
            <h2 className="font-display text-sm font-semibold">{t("dashboard.recommendations")}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{t("dashboard.recommendationsEmpty")}</p>
          </Card>
        </StaggerItem>
      </StaggerGroup>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: typeof Flame;
  label: string;
  value: string | null;
  accent: "amber" | "emerald";
}) {
  return (
    <Card className="hover-lift h-full p-5">
      <div
        className={`grid size-10 place-items-center rounded-xl ${
          accent === "amber" ? "bg-accent/12 text-accent" : "bg-primary/12 text-primary"
        }`}
      >
        <Icon className="size-5" />
      </div>
      <p className="mt-4 text-xs font-medium text-muted-foreground">{label}</p>
      {value ? (
        <p className="mt-0.5 font-display text-xl font-bold">{value}</p>
      ) : (
        <Skeleton className="mt-1.5 h-6 w-16" />
      )}
    </Card>
  );
}

function QuickAction({ to, icon: Icon, label }: { to: string; icon: typeof Sparkles; label: string }) {
  return (
    <Link
      to={to}
      className="hover-lift flex items-center gap-3 rounded-xl border border-border bg-secondary/30 px-3.5 py-3 text-sm font-medium transition-colors hover:bg-secondary/60"
    >
      <Icon className="size-4 text-primary" />
      <span className="flex-1">{label}</span>
      <ArrowRight className="size-4 text-muted-foreground" />
    </Link>
  );
}
