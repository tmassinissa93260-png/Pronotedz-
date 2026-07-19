import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase/client";

type SessionState = {
  session: Session | null;
  loading: boolean;
};

/** Live auth session, kept in sync via Supabase's onAuthStateChange (sign in/out, token refresh). */
export function useSession(): SessionState {
  const [state, setState] = useState<SessionState>({ session: null, loading: true });

  useEffect(() => {
    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (mounted) setState({ session: data.session, loading: false });
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (mounted) setState({ session, loading: false });
    });
    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  return state;
}
