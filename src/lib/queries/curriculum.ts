import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";
import type { Cycle } from "@/lib/curriculum/school-levels";

export type EduLevel = Database["public"]["Tables"]["edu_levels"]["Row"];
export type EduSubject = Database["public"]["Tables"]["edu_subjects"]["Row"];
export type EduChapter = Database["public"]["Tables"]["edu_chapters"]["Row"];
export type EduLesson = Database["public"]["Tables"]["edu_lessons"]["Row"];

export type LessonContent = { explanation: string; simplified?: string; key_points?: string[] };
export type LessonExercise = { question: string; correction: string; difficulty?: "facile" | "moyen" | "difficile" };
export type LessonSujet = { statement: string; correction: string };

async function fetchLevelsByCycle(cycle: Cycle): Promise<EduLevel[]> {
  const { data, error } = await supabase
    .from("edu_levels")
    .select("*")
    .eq("cycle", cycle)
    .order("order_index");
  if (error) throw error;
  return data ?? [];
}

export function levelsByCycleQueryOptions(cycle: Cycle) {
  return queryOptions({
    queryKey: ["curriculum", "levels", cycle],
    queryFn: () => fetchLevelsByCycle(cycle),
    staleTime: 5 * 60_000,
  });
}

async function fetchLevelBySlug(slug: string): Promise<EduLevel | null> {
  const { data, error } = await supabase.from("edu_levels").select("*").eq("slug", slug).maybeSingle();
  if (error) throw error;
  return data;
}

export function levelBySlugQueryOptions(slug: string) {
  return queryOptions({
    queryKey: ["curriculum", "level", slug],
    queryFn: () => fetchLevelBySlug(slug),
    staleTime: 5 * 60_000,
  });
}

async function fetchSubjectsByLevel(levelId: string): Promise<EduSubject[]> {
  const { data, error } = await supabase
    .from("edu_subjects")
    .select("*")
    .eq("level_id", levelId)
    .order("order_index");
  if (error) throw error;
  return data ?? [];
}

export function subjectsByLevelQueryOptions(levelId: string | undefined) {
  return queryOptions({
    queryKey: ["curriculum", "subjects", levelId],
    queryFn: () => fetchSubjectsByLevel(levelId as string),
    enabled: Boolean(levelId),
    staleTime: 5 * 60_000,
  });
}

async function fetchSubjectBySlug(levelId: string, slug: string): Promise<EduSubject | null> {
  const { data, error } = await supabase
    .from("edu_subjects")
    .select("*")
    .eq("level_id", levelId)
    .eq("slug", slug)
    .maybeSingle();
  if (error) throw error;
  return data;
}

export function subjectBySlugQueryOptions(levelId: string | undefined, slug: string) {
  return queryOptions({
    queryKey: ["curriculum", "subject", levelId, slug],
    queryFn: () => fetchSubjectBySlug(levelId as string, slug),
    enabled: Boolean(levelId),
    staleTime: 5 * 60_000,
  });
}

async function fetchChaptersBySubject(subjectId: string): Promise<EduChapter[]> {
  const { data, error } = await supabase
    .from("edu_chapters")
    .select("*")
    .eq("subject_id", subjectId)
    .order("order_index");
  if (error) throw error;
  return data ?? [];
}

export function chaptersBySubjectQueryOptions(subjectId: string | undefined) {
  return queryOptions({
    queryKey: ["curriculum", "chapters", subjectId],
    queryFn: () => fetchChaptersBySubject(subjectId as string),
    enabled: Boolean(subjectId),
    staleTime: 2 * 60_000,
  });
}

/** Groups chapters by trimestre. Chapters without a trimester land in group 0 ("non classé"). */
export function groupChaptersByTrimester(chapters: EduChapter[]): Map<number, EduChapter[]> {
  const groups = new Map<number, EduChapter[]>();
  for (const chapter of chapters) {
    const key = chapter.trimester ?? 0;
    const list = groups.get(key) ?? [];
    list.push(chapter);
    groups.set(key, list);
  }
  return new Map([...groups.entries()].sort(([a], [b]) => a - b));
}

async function fetchChapterById(chapterId: string): Promise<EduChapter | null> {
  const { data, error } = await supabase.from("edu_chapters").select("*").eq("id", chapterId).maybeSingle();
  if (error) throw error;
  return data;
}

export function chapterByIdQueryOptions(chapterId: string) {
  return queryOptions({
    queryKey: ["curriculum", "chapter", chapterId],
    queryFn: () => fetchChapterById(chapterId),
    staleTime: 2 * 60_000,
  });
}

async function fetchLessonsByChapter(chapterId: string): Promise<EduLesson[]> {
  const { data, error } = await supabase
    .from("edu_lessons")
    .select("*")
    .eq("chapter_id", chapterId)
    .order("order_index");
  if (error) throw error;
  return data ?? [];
}

export function lessonsByChapterQueryOptions(chapterId: string) {
  return queryOptions({
    queryKey: ["curriculum", "lessons", chapterId],
    queryFn: () => fetchLessonsByChapter(chapterId),
    staleTime: 60_000,
  });
}

async function fetchLessonById(lessonId: string): Promise<EduLesson | null> {
  const { data, error } = await supabase.from("edu_lessons").select("*").eq("id", lessonId).maybeSingle();
  if (error) throw error;
  return data;
}

export function lessonByIdQueryOptions(lessonId: string) {
  return queryOptions({
    queryKey: ["curriculum", "lesson", lessonId],
    queryFn: () => fetchLessonById(lessonId),
    staleTime: 60_000,
  });
}
