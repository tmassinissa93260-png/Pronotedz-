import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";

/** Keeps every member's pomodoro timer in sync (new phase started by anyone shows up for all). */
export function useGroupPomodoroRealtime(groupId: string) {
  const queryClient = useQueryClient();

  useEffect(() => {
    const channel = supabase
      .channel(`group-pomodoro-${groupId}`)
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "group_pomodoro_sessions", filter: `group_id=eq.${groupId}` },
        () => queryClient.invalidateQueries({ queryKey: ["groups", "pomodoro", groupId] }),
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [groupId, queryClient]);
}
