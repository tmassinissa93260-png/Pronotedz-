import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { Bell, CheckCheck, BellRing, BellOff } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useNotifications, useMarkNotificationRead, useMarkAllNotificationsRead } from "@/hooks/use-notifications";
import { usePushSubscription } from "@/hooks/use-push-subscription";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "à l'instant";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h`;
  return `${Math.floor(hours / 24)} j`;
}

export function NotificationsDropdown({ userId }: { userId: string }) {
  const { data: notifications } = useNotifications(userId);
  const markRead = useMarkNotificationRead(userId);
  const markAllRead = useMarkAllNotificationsRead(userId);
  const unreadCount = (notifications ?? []).filter((n) => !n.read_at).length;
  const push = usePushSubscription(userId);

  async function handleTogglePush() {
    try {
      const nowSubscribed = await push.toggle();
      toast.success(nowSubscribed ? "Notifications push activées." : "Notifications push désactivées.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible d'activer les notifications push.");
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
          <Bell className="size-4" />
          {unreadCount > 0 && <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-accent" />}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-border px-3.5 py-2.5">
          <span className="text-sm font-semibold">Notifications</span>
          {unreadCount > 0 && (
            <button
              onClick={() => markAllRead.mutate()}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <CheckCheck className="size-3.5" /> Tout marquer lu
            </button>
          )}
        </div>
        <div className="max-h-80 overflow-y-auto">
          {!notifications || notifications.length === 0 ? (
            <p className="px-3.5 py-6 text-center text-sm text-muted-foreground">Aucune notification.</p>
          ) : (
            notifications.map((n) => {
              const content = (
                <div
                  className={cn(
                    "flex flex-col gap-0.5 border-b border-border/60 px-3.5 py-3 text-left transition-colors last:border-0 hover:bg-secondary/50",
                    !n.read_at && "bg-primary/5",
                  )}
                >
                  <div className="flex items-center gap-2">
                    {!n.read_at && <span className="size-1.5 shrink-0 rounded-full bg-primary" />}
                    <span className="text-sm font-medium">{n.title}</span>
                  </div>
                  {n.body && <p className="text-xs text-muted-foreground">{n.body}</p>}
                  <span className="text-[10px] text-muted-foreground">{timeAgo(n.created_at)}</span>
                </div>
              );
              return n.link ? (
                <Link key={n.id} to={n.link} onClick={() => !n.read_at && markRead.mutate(n.id)} className="block">
                  {content}
                </Link>
              ) : (
                <button key={n.id} onClick={() => !n.read_at && markRead.mutate(n.id)} className="block w-full">
                  {content}
                </button>
              );
            })
          )}
        </div>
        {push.supported && (
          <button
            onClick={handleTogglePush}
            disabled={push.loading}
            className="flex w-full items-center gap-2 border-t border-border px-3.5 py-2.5 text-left text-xs text-muted-foreground transition-colors hover:bg-secondary/50 hover:text-foreground"
          >
            {push.subscribed ? <BellOff className="size-3.5" /> : <BellRing className="size-3.5" />}
            {push.subscribed ? "Désactiver les notifications push" : "Activer les notifications push"}
          </button>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
