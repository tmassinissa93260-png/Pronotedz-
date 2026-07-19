import { useEffect, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { pingStreak, markChapterComplete } from "@/lib/gamification/actions";

/** Pings the daily streak once per mount (call from the dashboard) — safe to call more than once, the RPC is idempotent for the same day. */
export function usePingStreakOnce(userId: string | undefined) {
  const queryClient = useQueryClient();
  const firedRef = useRef(false);

  useEffect(() => {
    if (!userId || firedRef.current) return;
    firedRef.current = true;
    pingStreak(userId)
      .then(() => queryClient.invalidateQueries({ queryKey: ["dashboard", userId] }))
      .catch(() => {
        // best-effort — a failed streak ping shouldn't surface as an error to the student
      });
  }, [userId, queryClient]);
}

export function useMarkChapterComplete(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (chapterId: string) => markChapterComplete(userId, chapterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard", userId] });
    },
  });
}
