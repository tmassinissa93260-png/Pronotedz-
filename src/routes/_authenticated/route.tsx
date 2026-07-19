import { createFileRoute, redirect } from "@tanstack/react-router";
import { supabase } from "@/lib/supabase/client";
import { currentUserQueryOptions } from "@/lib/queries/profile";
import { AuthenticatedShell } from "@/components/layout/authenticated-shell";

export const Route = createFileRoute("/_authenticated")({
  beforeLoad: async ({ location, context }) => {
    const { data: sessionData } = await supabase.auth.getSession();
    let user = sessionData.session?.user ?? null;
    if (!user) {
      const { data, error } = await supabase.auth.getUser();
      if (error || !data.user) {
        throw redirect({ to: "/auth", search: { mode: "signin" } });
      }
      user = data.user;
    }

    const profileData = await context.queryClient.ensureQueryData(currentUserQueryOptions(user.id));
    if (!profileData.onboarded && location.pathname !== "/onboarding") {
      throw redirect({ to: "/onboarding" });
    }

    return { user };
  },
  component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
  const { user } = Route.useRouteContext();
  return <AuthenticatedShell user={user} />;
}
