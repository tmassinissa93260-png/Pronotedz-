import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { TeacherCard } from "@/lib/queries/teachers";

async function fetchPendingTeachers(): Promise<TeacherCard[]> {
  const { data, error } = await supabase
    .from("teacher_profiles")
    .select("*, profile:profiles(id, full_name, avatar_url, wilaya)")
    .eq("verification_status", "pending")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as unknown as TeacherCard[];
}

export function pendingTeachersQueryOptions() {
  return queryOptions({
    queryKey: ["moderation", "pending-teachers"],
    queryFn: fetchPendingTeachers,
    staleTime: 30_000,
  });
}
