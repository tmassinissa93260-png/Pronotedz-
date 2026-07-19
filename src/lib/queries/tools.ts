import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type ExamCountdown = Database["public"]["Tables"]["exam_countdowns"]["Row"];
export type MemoSheet = Database["public"]["Tables"]["memo_sheets"]["Row"];

async function fetchExamCountdowns(): Promise<ExamCountdown[]> {
  const { data, error } = await supabase
    .from("exam_countdowns")
    .select("*")
    .gte("exam_date", new Date().toISOString().slice(0, 10))
    .order("exam_date");
  if (error) throw error;
  return data ?? [];
}

export function examCountdownsQueryOptions() {
  return queryOptions({
    queryKey: ["tools", "countdowns"],
    queryFn: fetchExamCountdowns,
    staleTime: 5 * 60_000,
  });
}

async function fetchMemoSheets(studentId: string): Promise<MemoSheet[]> {
  const { data, error } = await supabase
    .from("memo_sheets")
    .select("*")
    .eq("student_id", studentId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data ?? [];
}

export function memoSheetsQueryOptions(studentId: string | undefined) {
  return queryOptions({
    queryKey: ["tools", "memo-sheets", studentId],
    queryFn: () => fetchMemoSheets(studentId as string),
    enabled: Boolean(studentId),
    staleTime: 30_000,
  });
}

async function fetchMemoSheet(sheetId: string): Promise<MemoSheet | null> {
  const { data, error } = await supabase.from("memo_sheets").select("*").eq("id", sheetId).maybeSingle();
  if (error) throw error;
  return data;
}

export function memoSheetQueryOptions(sheetId: string) {
  return queryOptions({
    queryKey: ["tools", "memo-sheet", sheetId],
    queryFn: () => fetchMemoSheet(sheetId),
    staleTime: 30_000,
  });
}
