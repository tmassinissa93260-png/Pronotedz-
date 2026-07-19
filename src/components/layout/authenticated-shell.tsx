import { Outlet, useNavigate } from "@tanstack/react-router";
import type { User } from "@supabase/supabase-js";
import { toast } from "sonner";
import { signOut } from "@/lib/auth/actions";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useDashboard } from "@/hooks/use-dashboard";
import { SidebarProvider, useSidebar } from "./sidebar-context";
import { AppSidebar } from "./app-sidebar";
import { MobileTabBar } from "./mobile-tab-bar";
import { MobileNavSheet } from "./mobile-nav-sheet";
import { Header } from "./header";
import { useT } from "@/lib/i18n";

function ShellInner({ user }: { user: User }) {
  const navigate = useNavigate();
  const t = useT();
  const { data } = useCurrentUser();
  const { data: dashboard } = useDashboard(user.id);
  const { setMobileOpen } = useSidebar();

  const isTeacher = data?.roles.includes("teacher") ?? false;
  const isAdmin = data?.roles.includes("admin") ?? false;

  async function handleSignOut() {
    try {
      await signOut();
      navigate({ to: "/" });
    } catch {
      toast.error(t("common.somethingWrong"));
    }
  }

  return (
    <div className="flex min-h-screen w-full bg-background">
      <AppSidebar isTeacher={isTeacher} isAdmin={isAdmin} />
      <MobileNavSheet isTeacher={isTeacher} isAdmin={isAdmin} onSignOut={handleSignOut} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          user={user}
          profile={data?.profile ?? null}
          dashboard={dashboard}
          onSignOut={handleSignOut}
          onOpenMobileNav={() => setMobileOpen(true)}
        />
        <main className="flex-1 pb-20 md:pb-0">
          <Outlet />
        </main>
        <MobileTabBar />
      </div>
    </div>
  );
}

export function AuthenticatedShell({ user }: { user: User }) {
  return (
    <SidebarProvider>
      <ShellInner user={user} />
    </SidebarProvider>
  );
}
