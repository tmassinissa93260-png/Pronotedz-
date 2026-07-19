import { supabase } from "@/lib/supabase/client";
import type { SchoolLevel, ExamTarget } from "@/lib/curriculum/school-levels";
import type { Lang } from "@/lib/i18n";

export type Role = "student" | "teacher" | "parent";

export type OnboardingPayload = {
  userId: string;
  role: Role;
  schoolLevel: SchoolLevel;
  examTarget: ExamTarget;
  wilaya: string;
  language: Lang;
  teacher?: {
    subjects: string[];
    hourlyRate: number;
    idDocFile: File | null;
    diplomaFile: File | null;
  };
};

async function uploadTeacherDoc(userId: string, file: File, kind: "id" | "diploma") {
  const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, "_");
  const path = `${userId}/${kind}-${Date.now()}-${safeName}`;
  const { error } = await supabase.storage.from("teacher-docs").upload(path, file, { upsert: true });
  if (error) throw error;
  return path;
}

/** Persists onboarding answers against the existing production schema. Additive-only: no new tables. */
export async function submitOnboarding(payload: OnboardingPayload): Promise<{ redirectTo: string }> {
  const { userId, role, schoolLevel, examTarget, wilaya, language, teacher } = payload;

  if (role !== "student") {
    const { error } = await supabase
      .from("user_roles")
      .upsert({ user_id: userId, role }, { onConflict: "user_id,role" });
    if (error) throw error;
  }

  const { error: profileError } = await supabase
    .from("profiles")
    .update({ wilaya: wilaya || null, language })
    .eq("id", userId);
  if (profileError) throw profileError;

  const { error: studentError } = await supabase.from("student_profiles").upsert({
    user_id: userId,
    school_level: schoolLevel,
    exam_target: examTarget,
    preferred_language: language,
  });
  if (studentError) throw studentError;

  const ref = window.localStorage.getItem("estadi_ref");
  if (ref) {
    try {
      await supabase.rpc("redeem_referral_code", { _code: ref.trim().toLowerCase(), _new_user: userId });
    } catch {
      // best-effort — an invalid/expired code shouldn't block onboarding
    }
    window.localStorage.removeItem("estadi_ref");
  }

  if (role === "teacher" && teacher) {
    const [idPath, diplomaPath] = await Promise.all([
      teacher.idDocFile ? uploadTeacherDoc(userId, teacher.idDocFile, "id") : Promise.resolve(undefined),
      teacher.diplomaFile
        ? uploadTeacherDoc(userId, teacher.diplomaFile, "diploma")
        : Promise.resolve(undefined),
    ]);
    const { error: teacherError } = await supabase.from("teacher_profiles").upsert({
      user_id: userId,
      subjects: teacher.subjects,
      levels: [schoolLevel],
      hourly_rate: teacher.hourlyRate,
      id_document_url: idPath ?? null,
      diploma_url: diplomaPath ?? null,
      verification_status: "pending",
    });
    if (teacherError) throw teacherError;
    return { redirectTo: "/teacher" };
  }

  return { redirectTo: "/dashboard" };
}
