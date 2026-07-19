import { createFileRoute, redirect } from "@tanstack/react-router";
import { supabase } from "@/lib/supabase/client";
import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard";

export const Route = createFileRoute("/onboarding")({
  beforeLoad: async () => {
    const { data: sessionData } = await supabase.auth.getSession();
    const user = sessionData.session?.user;
    if (!user) throw redirect({ to: "/auth", search: { mode: "signin" } });
    return { user };
  },
  component: OnboardingRoute,
});

function OnboardingRoute() {
  const { user } = Route.useRouteContext();
  return <OnboardingWizard userId={user.id} />;
}
