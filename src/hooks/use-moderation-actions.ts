import { useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { PostReport } from "@/lib/queries/moderation";

async function hideContent(targetType: string, targetId: string) {
  const table = targetType === "thread" ? "community_threads" : "community_posts";
  const { error } = await supabase.from(table).update({ hidden: true }).eq("id", targetId);
  if (error) throw error;
}

async function resolveReport(reportId: string, status: "resolved") {
  const { error } = await supabase
    .from("post_reports")
    .update({ status, resolved_at: new Date().toISOString() })
    .eq("id", reportId);
  if (error) throw error;
}

export function useResolveReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ report, hide }: { report: PostReport; hide: boolean }) => {
      if (hide) await hideContent(report.target_type, report.target_id);
      await resolveReport(report.id, "resolved");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["moderation", "reports"] });
      queryClient.invalidateQueries({ queryKey: ["community"] });
    },
  });
}
