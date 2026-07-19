import { Link } from "@tanstack/react-router";
import { Flame, Zap, Bell, LogOut, User as UserIcon } from "lucide-react";
import type { User } from "@supabase/supabase-js";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { LanguageSwitcher } from "@/components/language-switcher";
import { ThemeToggle } from "@/components/theme-toggle";
import { useT } from "@/lib/i18n";
import type { Profile } from "@/lib/queries/profile";
import type { DashboardData } from "@/lib/queries/dashboard";

function initials(name: string | null | undefined, email: string | undefined) {
  const source = name?.trim() || email || "?";
  return source
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function Header({
  user,
  profile,
  dashboard,
  onSignOut,
  onOpenMobileNav,
}: {
  user: User;
  profile: Profile | null;
  dashboard: DashboardData | undefined;
  onSignOut: () => void;
  onOpenMobileNav: () => void;
}) {
  const t = useT();

  return (
    <header className="glass sticky top-0 z-30 flex h-14 items-center gap-2 px-4">
      <button
        onClick={onOpenMobileNav}
        className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground md:hidden"
        aria-label="Menu"
      >
        <div className="flex flex-col gap-1">
          <span className="h-0.5 w-4 rounded-full bg-current" />
          <span className="h-0.5 w-4 rounded-full bg-current" />
          <span className="h-0.5 w-4 rounded-full bg-current" />
        </div>
      </button>

      <div className="ml-auto flex items-center gap-1.5">
        {dashboard && (
          <div className="hidden items-center gap-1.5 sm:flex">
            <span className="inline-flex items-center gap-1 rounded-full bg-accent/12 px-2.5 py-1 text-xs font-semibold text-accent">
              <Flame className="size-3.5" /> {dashboard.streakDays}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/12 px-2.5 py-1 text-xs font-semibold text-primary">
              <Zap className="size-3.5" /> {dashboard.xp} XP
            </span>
          </div>
        )}

        <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
          <Bell className="size-4" />
          {dashboard && dashboard.unreadNotifications > 0 && (
            <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-accent" />
          )}
        </Button>

        <LanguageSwitcher compact />
        <ThemeToggle />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="ml-1 outline-none">
              <Avatar className="size-8">
                <AvatarFallback>{initials(profile?.full_name, user.email)}</AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <div className="px-2.5 py-1.5">
              <p className="truncate text-sm font-medium">{profile?.full_name || user.email}</p>
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link to="/dashboard">
                <UserIcon className="size-4" /> {t("nav.dashboard")}
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={onSignOut} className="text-destructive focus:text-destructive">
              <LogOut className="size-4" /> {t("common.signOut")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
