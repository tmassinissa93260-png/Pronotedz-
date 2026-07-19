import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

type SchoolLevel = Database["public"]["Enums"]["school_level"];
type PriceType = Database["public"]["Enums"]["price_type"];
type LanguageCode = Database["public"]["Enums"]["language_code"];

export type CreateCoursePayload = {
  teacherId: string;
  title: string;
  description: string | null;
  subject: string;
  level: SchoolLevel;
  language: LanguageCode;
  price: number;
  priceType: PriceType;
  trailerVideoUrl: string;
  thumbnailUrl: string | null;
};

export async function createCourse(payload: CreateCoursePayload): Promise<{ id: string }> {
  const { data, error } = await supabase
    .from("courses")
    .insert({
      teacher_id: payload.teacherId,
      title: payload.title.trim(),
      description: payload.description,
      subject: payload.subject.trim(),
      level: payload.level,
      language: payload.language,
      price: payload.price,
      price_type: payload.priceType,
      trailer_video_url: payload.trailerVideoUrl.trim(),
      thumbnail_url: payload.thumbnailUrl,
      status: "draft",
    })
    .select("id")
    .single();
  if (error) throw error;
  return { id: data.id };
}

export async function setCourseStatus(courseId: string, status: "draft" | "published" | "archived"): Promise<void> {
  const { error } = await supabase.from("courses").update({ status }).eq("id", courseId);
  if (error) throw error;
}

export type AddVideoPayload = {
  courseId: string;
  title: string;
  videoUrl: string;
  durationSec: number | null;
  orderIndex: number;
  isFreePreview: boolean;
};

export async function addCourseVideo(payload: AddVideoPayload): Promise<void> {
  const { error } = await supabase.from("course_videos").insert({
    course_id: payload.courseId,
    title: payload.title.trim(),
    video_url: payload.videoUrl.trim(),
    duration_sec: payload.durationSec,
    order_index: payload.orderIndex,
    is_free_preview: payload.isFreePreview,
  });
  if (error) throw error;
}

export async function deleteCourseVideo(videoId: string): Promise<void> {
  const { error } = await supabase.from("course_videos").delete().eq("id", videoId);
  if (error) throw error;
}

export async function enrollInCourse(courseId: string, studentId: string): Promise<{ alreadyEnrolled: boolean }> {
  const { data: existing } = await supabase
    .from("course_enrollments")
    .select("id")
    .eq("course_id", courseId)
    .eq("student_id", studentId)
    .maybeSingle();
  if (existing) return { alreadyEnrolled: true };

  // courses.enrolled_count is kept in sync by a DB trigger (see migrations) —
  // nothing to do here beyond the insert itself.
  const { error } = await supabase.from("course_enrollments").insert({ course_id: courseId, student_id: studentId });
  if (error) throw error;
  return { alreadyEnrolled: false };
}
