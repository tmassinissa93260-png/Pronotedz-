import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type ExamArchiveEntry = Database["public"]["Tables"]["exam_archive"]["Row"];
export type ExamType = Database["public"]["Enums"]["exam_target"];

function dedupe(values: (string | null)[]): string[] {
  return [...new Set(values.filter((v): v is string => Boolean(v)))].sort();
}

/** Filière options actually present in the archive for this exam type — never hardcoded, always what's really there. */
async function fetchFilieres(examType: ExamType): Promise<string[]> {
  const { data, error } = await supabase
    .from("exam_archive")
    .select("filiere")
    .eq("exam_type", examType)
    .eq("status", "published");
  if (error) throw error;
  return dedupe((data ?? []).map((r) => r.filiere));
}

export function filieresQueryOptions(examType: ExamType) {
  return queryOptions({
    queryKey: ["archive", "filieres", examType],
    queryFn: () => fetchFilieres(examType),
    staleTime: 5 * 60_000,
  });
}

async function fetchSubjects(examType: ExamType, filiere: string | null): Promise<string[]> {
  let query = supabase.from("exam_archive").select("subject").eq("exam_type", examType).eq("status", "published");
  query = filiere ? query.eq("filiere", filiere) : query.is("filiere", null);
  const { data, error } = await query;
  if (error) throw error;
  return dedupe((data ?? []).map((r) => r.subject));
}

export function subjectsQueryOptions(examType: ExamType, filiere: string | null) {
  return queryOptions({
    queryKey: ["archive", "subjects", examType, filiere],
    queryFn: () => fetchSubjects(examType, filiere),
    staleTime: 5 * 60_000,
  });
}

async function fetchEntries(examType: ExamType, filiere: string | null, subject: string): Promise<ExamArchiveEntry[]> {
  let query = supabase
    .from("exam_archive")
    .select("*")
    .eq("exam_type", examType)
    .eq("subject", subject)
    .eq("status", "published")
    .order("year", { ascending: false });
  query = filiere ? query.eq("filiere", filiere) : query.is("filiere", null);
  const { data, error } = await query;
  if (error) throw error;
  return data ?? [];
}

export function entriesQueryOptions(examType: ExamType, filiere: string | null, subject: string) {
  return queryOptions({
    queryKey: ["archive", "entries", examType, filiere, subject],
    queryFn: () => fetchEntries(examType, filiere, subject),
    enabled: Boolean(subject),
    staleTime: 2 * 60_000,
  });
}

async function fetchSignedUrl(path: string): Promise<string> {
  const { data, error } = await supabase.storage.from("exam-archive").createSignedUrl(path, 3600);
  if (error) throw error;
  return data.signedUrl;
}

export function signedArchiveUrlQueryOptions(path: string | null) {
  return queryOptions({
    queryKey: ["archive", "signed-url", path],
    queryFn: () => fetchSignedUrl(path as string),
    enabled: Boolean(path),
    staleTime: 50 * 60_000,
  });
}

async function fetchPendingSubmissions(): Promise<ExamArchiveEntry[]> {
  const { data, error } = await supabase
    .from("exam_archive")
    .select("*")
    .eq("status", "pending")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data ?? [];
}

export function pendingSubmissionsQueryOptions() {
  return queryOptions({
    queryKey: ["archive", "pending"],
    queryFn: fetchPendingSubmissions,
    staleTime: 30_000,
  });
}
