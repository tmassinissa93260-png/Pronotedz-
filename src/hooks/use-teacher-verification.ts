import { useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";

export function useSetTeacherVerification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ teacherId, status }: { teacherId: string; status: "verified" | "rejected" }) => {
      const { error } = await supabase.from("teacher_profiles").update({ verification_status: status }).eq("user_id", teacherId);
      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["moderation", "pending-teachers"] });
      queryClient.invalidateQueries({ queryKey: ["teachers"] });
    },
  });
}
