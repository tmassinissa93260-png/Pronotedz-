import { useQuery } from "@tanstack/react-query";
import { useSession } from "./use-session";
import { currentUserQueryOptions } from "@/lib/queries/profile";

/** Session + profile/roles data for the signed-in user, cached via TanStack Query. */
export function useCurrentUser() {
  const { session, loading: sessionLoading } = useSession();
  const query = useQuery(currentUserQueryOptions(session?.user.id));

  return {
    user: session?.user ?? null,
    session,
    ...query,
    data: query.data,
    isLoading: sessionLoading || (Boolean(session) && query.isLoading),
  };
}
