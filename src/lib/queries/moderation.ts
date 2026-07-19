import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type PostReport = Database["public"]["Tables"]["post_reports"]["Row"];

async function fetchOpenReports(): Promise<PostReport[]> {
  const { data, error } = await supabase
    .from("post_reports")
    .select("*")
    .eq("status", "open")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data ?? [];
}

export function openReportsQueryOptions() {
  return queryOptions({
    queryKey: ["moderation", "reports"],
    queryFn: fetchOpenReports,
    staleTime: 30_000,
  });
}
