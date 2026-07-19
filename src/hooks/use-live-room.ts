import { useMutation } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";

type RoomResponse = { url?: string; error?: string; opensInMin?: number };

export function useJoinLiveRoom(sessionId: string) {
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await supabase.functions.invoke<RoomResponse>("live-session-room", {
        body: { sessionId },
      });
      if (error) throw error;
      if (!data?.url) {
        const err = new Error(data?.error ?? "Impossible de rejoindre la session.") as Error & { opensInMin?: number };
        err.opensInMin = data?.opensInMin;
        throw err;
      }
      return data.url;
    },
  });
}
