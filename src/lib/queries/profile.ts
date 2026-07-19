import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type Profile = Database["public"]["Tables"]["profiles"]["Row"];
export type StudentProfile = Database["public"]["Tables"]["student_profiles"]["Row"];
export type TeacherProfile = Database["public"]["Tables"]["teacher_profiles"]["Row"];
export type AppRole = Database["public"]["Enums"]["app_role"];

export type CurrentUserData = {
  profile: Profile | null;
  studentProfile: StudentProfile | null;
  teacherProfile: TeacherProfile | null;
  roles: AppRole[];
  /** true once the student has picked a school level, i.e. finished onboarding */
  onboarded: boolean;
};

async function fetchCurrentUserData(userId: string): Promise<CurrentUserData> {
  const [{ data: profile }, { data: studentProfile }, { data: teacherProfile }, { data: roleRows }] =
    await Promise.all([
      supabase.from("profiles").select("*").eq("id", userId).maybeSingle(),
      supabase.from("student_profiles").select("*").eq("user_id", userId).maybeSingle(),
      supabase.from("teacher_profiles").select("*").eq("user_id", userId).maybeSingle(),
      supabase.from("user_roles").select("role").eq("user_id", userId),
    ]);

  const roles = (roleRows ?? []).map((r) => r.role);

  return {
    profile: profile ?? null,
    studentProfile: studentProfile ?? null,
    teacherProfile: teacherProfile ?? null,
    roles,
    onboarded: Boolean(studentProfile?.school_level) || roles.includes("teacher"),
  };
}

export function currentUserQueryOptions(userId: string | undefined) {
  return queryOptions({
    queryKey: ["current-user", userId],
    queryFn: () => fetchCurrentUserData(userId as string),
    enabled: Boolean(userId),
    staleTime: 60_000,
  });
}
