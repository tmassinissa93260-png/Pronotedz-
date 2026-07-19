import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type TeacherProfile = Database["public"]["Tables"]["teacher_profiles"]["Row"];
export type Profile = Database["public"]["Tables"]["profiles"]["Row"];
export type TeacherAvailability = Database["public"]["Tables"]["teacher_availability"]["Row"];
export type LiveSession = Database["public"]["Tables"]["live_sessions"]["Row"];
export type SessionReview = Database["public"]["Tables"]["session_reviews"]["Row"];

export type TeacherCard = TeacherProfile & { profile: Pick<Profile, "id" | "full_name" | "avatar_url" | "wilaya"> | null };

async function fetchTeachers(subjectFilter: string): Promise<TeacherCard[]> {
  let query = supabase
    .from("teacher_profiles")
    .select("*, profile:profiles(id, full_name, avatar_url, wilaya)")
    .eq("verification_status", "verified")
    .order("rating_avg", { ascending: false });
  if (subjectFilter.trim()) {
    query = query.contains("subjects", [subjectFilter.trim()]);
  }
  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as unknown as TeacherCard[];
}

export function teachersQueryOptions(subjectFilter: string) {
  return queryOptions({
    queryKey: ["teachers", "list", subjectFilter],
    queryFn: () => fetchTeachers(subjectFilter),
    staleTime: 60_000,
  });
}

async function fetchTeacherProfile(teacherId: string): Promise<TeacherCard | null> {
  const { data, error } = await supabase
    .from("teacher_profiles")
    .select("*, profile:profiles(id, full_name, avatar_url, wilaya)")
    .eq("user_id", teacherId)
    .maybeSingle();
  if (error) throw error;
  return data as unknown as TeacherCard | null;
}

export function teacherProfileQueryOptions(teacherId: string) {
  return queryOptions({
    queryKey: ["teachers", "profile", teacherId],
    queryFn: () => fetchTeacherProfile(teacherId),
    staleTime: 60_000,
  });
}

async function fetchTeacherAvailability(teacherId: string): Promise<TeacherAvailability[]> {
  const { data, error } = await supabase
    .from("teacher_availability")
    .select("*")
    .eq("teacher_id", teacherId)
    .order("day_of_week")
    .order("start_time");
  if (error) throw error;
  return data ?? [];
}

export function teacherAvailabilityQueryOptions(teacherId: string) {
  return queryOptions({
    queryKey: ["teachers", "availability", teacherId],
    queryFn: () => fetchTeacherAvailability(teacherId),
    staleTime: 60_000,
  });
}

export type OpenSlot = LiveSession & { booked: number };

async function fetchOpenSlots(teacherId: string): Promise<OpenSlot[]> {
  const nowIso = new Date().toISOString();
  const { data: sessions, error } = await supabase
    .from("live_sessions")
    .select("*")
    .eq("teacher_id", teacherId)
    .gte("scheduled_at", nowIso)
    .in("status", ["scheduled", "live"])
    .order("scheduled_at");
  if (error) throw error;
  const ids = (sessions ?? []).map((s) => s.id);
  const counts: Record<string, number> = {};
  if (ids.length) {
    const { data: bookings } = await supabase
      .from("session_bookings")
      .select("session_id")
      .in("session_id", ids)
      .in("status", ["booked", "attended"]);
    for (const b of bookings ?? []) counts[b.session_id] = (counts[b.session_id] ?? 0) + 1;
  }
  return (sessions ?? []).map((s) => ({ ...s, booked: counts[s.id] ?? 0 }));
}

export function openSlotsQueryOptions(teacherId: string) {
  return queryOptions({
    queryKey: ["teachers", "open-slots", teacherId],
    queryFn: () => fetchOpenSlots(teacherId),
    staleTime: 30_000,
  });
}

async function fetchReviews(teacherId: string): Promise<SessionReview[]> {
  const { data, error } = await supabase
    .from("session_reviews")
    .select("*")
    .eq("teacher_id", teacherId)
    .order("created_at", { ascending: false })
    .limit(20);
  if (error) throw error;
  return data ?? [];
}

export function teacherReviewsQueryOptions(teacherId: string) {
  return queryOptions({
    queryKey: ["teachers", "reviews", teacherId],
    queryFn: () => fetchReviews(teacherId),
    staleTime: 60_000,
  });
}

export type TeacherScheduleSession = LiveSession & {
  bookings: { id: string; student_id: string; status: string; student: Pick<Profile, "full_name" | "avatar_url"> | null }[];
};

async function fetchTeacherSchedule(teacherId: string): Promise<TeacherScheduleSession[]> {
  const { data: sessions, error } = await supabase
    .from("live_sessions")
    .select("*")
    .eq("teacher_id", teacherId)
    .gte("scheduled_at", new Date(Date.now() - 24 * 3600 * 1000).toISOString())
    .order("scheduled_at");
  if (error) throw error;
  const ids = (sessions ?? []).map((s) => s.id);
  if (!ids.length) return [];

  const { data: bookings } = await supabase
    .from("session_bookings")
    .select("id, session_id, student_id, status")
    .in("session_id", ids)
    .in("status", ["booked", "attended"]);

  const studentIds = [...new Set((bookings ?? []).map((b) => b.student_id))];
  const { data: profiles } = studentIds.length
    ? await supabase.from("profiles").select("id, full_name, avatar_url").in("id", studentIds)
    : { data: [] as Pick<Profile, "id" | "full_name" | "avatar_url">[] };
  const profileMap = new Map((profiles ?? []).map((p) => [p.id, p]));

  return (sessions ?? []).map((s) => ({
    ...s,
    bookings: (bookings ?? [])
      .filter((b) => b.session_id === s.id)
      .map((b) => ({ ...b, student: profileMap.get(b.student_id) ?? null })),
  }));
}

export function teacherScheduleQueryOptions(teacherId: string | undefined) {
  return queryOptions({
    queryKey: ["sessions", "teacher-schedule", teacherId],
    queryFn: () => fetchTeacherSchedule(teacherId as string),
    enabled: Boolean(teacherId),
    staleTime: 30_000,
  });
}

async function fetchMyBookedSessionIds(studentId: string): Promise<Set<string>> {
  const { data, error } = await supabase
    .from("session_bookings")
    .select("session_id")
    .eq("student_id", studentId)
    .in("status", ["booked", "attended"]);
  if (error) throw error;
  return new Set((data ?? []).map((b) => b.session_id));
}

export type SessionDetail = {
  session: LiveSession;
  bookedCount: number;
  isTeacher: boolean;
  myBooking: { id: string; status: string } | null;
};

async function fetchSessionDetail(sessionId: string, userId: string): Promise<SessionDetail | null> {
  const { data: session, error } = await supabase.from("live_sessions").select("*").eq("id", sessionId).maybeSingle();
  if (error) throw error;
  if (!session) return null;

  const [{ count }, { data: myBooking }] = await Promise.all([
    supabase
      .from("session_bookings")
      .select("id", { count: "exact", head: true })
      .eq("session_id", sessionId)
      .in("status", ["booked", "attended"]),
    supabase
      .from("session_bookings")
      .select("id, status")
      .eq("session_id", sessionId)
      .eq("student_id", userId)
      .maybeSingle(),
  ]);

  return {
    session,
    bookedCount: count ?? 0,
    isTeacher: session.teacher_id === userId,
    myBooking,
  };
}

export function sessionDetailQueryOptions(sessionId: string, userId: string) {
  return queryOptions({
    queryKey: ["sessions", "detail", sessionId],
    queryFn: () => fetchSessionDetail(sessionId, userId),
    enabled: Boolean(sessionId && userId),
    staleTime: 15_000,
    refetchInterval: 15_000,
  });
}

export function myBookedSessionIdsQueryOptions(studentId: string | undefined) {
  return queryOptions({
    queryKey: ["sessions", "my-booked-ids", studentId],
    queryFn: () => fetchMyBookedSessionIds(studentId as string),
    enabled: Boolean(studentId),
    staleTime: 30_000,
  });
}
