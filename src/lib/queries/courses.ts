import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type Course = Database["public"]["Tables"]["courses"]["Row"];
export type CourseVideo = Database["public"]["Tables"]["course_videos"]["Row"];
export type CourseReview = Database["public"]["Tables"]["course_reviews"]["Row"];
export type Profile = Database["public"]["Tables"]["profiles"]["Row"];

export type CourseCard = Course & { teacher: Pick<Profile, "full_name" | "avatar_url"> | null };

async function fetchPublishedCourses(subjectFilter: string): Promise<CourseCard[]> {
  let query = supabase
    .from("courses")
    .select("*, teacher:profiles(full_name, avatar_url)")
    .eq("status", "published")
    .order("enrolled_count", { ascending: false });
  if (subjectFilter.trim()) query = query.ilike("subject", `%${subjectFilter.trim()}%`);
  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as unknown as CourseCard[];
}

export function publishedCoursesQueryOptions(subjectFilter: string) {
  return queryOptions({
    queryKey: ["courses", "published", subjectFilter],
    queryFn: () => fetchPublishedCourses(subjectFilter),
    staleTime: 60_000,
  });
}

async function fetchCourse(courseId: string): Promise<CourseCard | null> {
  const { data, error } = await supabase
    .from("courses")
    .select("*, teacher:profiles(full_name, avatar_url)")
    .eq("id", courseId)
    .maybeSingle();
  if (error) throw error;
  return data as unknown as CourseCard | null;
}

export function courseQueryOptions(courseId: string) {
  return queryOptions({
    queryKey: ["courses", "detail", courseId],
    queryFn: () => fetchCourse(courseId),
    staleTime: 30_000,
  });
}

async function fetchCourseVideos(courseId: string): Promise<CourseVideo[]> {
  const { data, error } = await supabase
    .from("course_videos")
    .select("*")
    .eq("course_id", courseId)
    .order("order_index");
  if (error) throw error;
  return data ?? [];
}

export function courseVideosQueryOptions(courseId: string) {
  return queryOptions({
    queryKey: ["courses", "videos", courseId],
    queryFn: () => fetchCourseVideos(courseId),
    staleTime: 30_000,
  });
}

async function fetchCourseReviews(courseId: string): Promise<CourseReview[]> {
  const { data, error } = await supabase
    .from("course_reviews")
    .select("*")
    .eq("course_id", courseId)
    .order("created_at", { ascending: false })
    .limit(20);
  if (error) throw error;
  return data ?? [];
}

export function courseReviewsQueryOptions(courseId: string) {
  return queryOptions({
    queryKey: ["courses", "reviews", courseId],
    queryFn: () => fetchCourseReviews(courseId),
    staleTime: 60_000,
  });
}

async function fetchMyEnrollment(courseId: string, studentId: string) {
  const { data, error } = await supabase
    .from("course_enrollments")
    .select("id, progress_pct")
    .eq("course_id", courseId)
    .eq("student_id", studentId)
    .maybeSingle();
  if (error) throw error;
  return data;
}

export function myEnrollmentQueryOptions(courseId: string, studentId: string | undefined) {
  return queryOptions({
    queryKey: ["courses", "my-enrollment", courseId, studentId],
    queryFn: () => fetchMyEnrollment(courseId, studentId as string),
    enabled: Boolean(studentId),
    staleTime: 30_000,
  });
}

async function fetchTeacherCourses(teacherId: string): Promise<Course[]> {
  const { data, error } = await supabase
    .from("courses")
    .select("*")
    .eq("teacher_id", teacherId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data ?? [];
}

export function teacherCoursesQueryOptions(teacherId: string | undefined) {
  return queryOptions({
    queryKey: ["courses", "teacher", teacherId],
    queryFn: () => fetchTeacherCourses(teacherId as string),
    enabled: Boolean(teacherId),
    staleTime: 30_000,
  });
}
