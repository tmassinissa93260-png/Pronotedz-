import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type StudentTask = Database["public"]["Tables"]["student_tasks"]["Row"];

async function fetchMyTasks(studentId: string): Promise<StudentTask[]> {
  const { data, error } = await supabase
    .from("student_tasks")
    .select("*")
    .eq("student_id", studentId)
    .order("status", { ascending: true })
    .order("due_at", { ascending: true, nullsFirst: false });
  if (error) throw error;
  return data ?? [];
}

export function myTasksQueryOptions(studentId: string | undefined) {
  return queryOptions({
    queryKey: ["tasks", "mine", studentId],
    queryFn: () => fetchMyTasks(studentId as string),
    enabled: Boolean(studentId),
    staleTime: 15_000,
  });
}
