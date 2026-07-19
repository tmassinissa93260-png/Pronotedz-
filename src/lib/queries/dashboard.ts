import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";

export type UpcomingSession = {
  bookingId: string;
  sessionId: string;
  title: string | null;
  subject: string;
  scheduledAt: string;
  durationMin: number;
};

export type DashboardData = {
  streakDays: number;
  xp: number;
  badgeCount: number;
  unreadNotifications: number;
  upcomingSessions: UpcomingSession[];
};

async function fetchDashboardData(userId: string): Promise<DashboardData> {
  const [{ data: studentProfile }, { data: gamification }, { data: bookings }, { count: unread }] =
    await Promise.all([
      supabase.from("student_profiles").select("streak_days").eq("user_id", userId).maybeSingle(),
      supabase
        .from("gamification")
        .select("badges, chapters_completed, xp")
        .eq("student_id", userId)
        .maybeSingle(),
      supabase
        .from("session_bookings")
        .select("id, session_id, live_sessions(title, subject, scheduled_at, duration_min)")
        .eq("student_id", userId)
        .eq("status", "booked")
        .gte("live_sessions.scheduled_at", new Date().toISOString())
        .order("created_at", { ascending: true })
        .limit(3),
      supabase
        .from("notifications")
        .select("id", { count: "exact", head: true })
        .eq("user_id", userId)
        .is("read_at", null),
    ]);

  const badgeCount = Array.isArray(gamification?.badges) ? gamification.badges.length : 0;

  const upcomingSessions: UpcomingSession[] = (bookings ?? [])
    .filter((b) => b.live_sessions)
    .map((b) => ({
      bookingId: b.id,
      sessionId: b.session_id,
      title: b.live_sessions!.title,
      subject: b.live_sessions!.subject,
      scheduledAt: b.live_sessions!.scheduled_at,
      durationMin: b.live_sessions!.duration_min,
    }));

  return {
    streakDays: studentProfile?.streak_days ?? 0,
    xp: gamification?.xp ?? 0,
    badgeCount,
    unreadNotifications: unread ?? 0,
    upcomingSessions,
  };
}

export function dashboardQueryOptions(userId: string | undefined) {
  return queryOptions({
    queryKey: ["dashboard", userId],
    queryFn: () => fetchDashboardData(userId as string),
    enabled: Boolean(userId),
    staleTime: 30_000,
  });
}
