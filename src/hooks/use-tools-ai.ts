import { useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { MemoSheet } from "@/lib/queries/tools";

export type HomeworkResult = { explanation: string; steps: string[]; answer: string };

export function useHomeworkHelp(userId: string) {
  return useMutation({
    mutationFn: async ({ file, question }: { file: File; question: string }) => {
      const ext = file.name.split(".").pop()?.replace(/[^a-zA-Z0-9]/g, "") || "jpg";
      const path = `${userId}/${crypto.randomUUID()}.${ext}`;
      const { error: uploadError } = await supabase.storage.from("ai-uploads").upload(path, file);
      if (uploadError) throw uploadError;

      const { data, error } = await supabase.functions.invoke<{ result: HomeworkResult; error?: string }>("tools-ai", {
        body: { action: "homework", imagePath: path, question },
      });
      if (error) throw error;
      if (!data?.result) throw new Error(data?.error ?? "Impossible d'analyser cette photo.");
      return data.result;
    },
  });
}

export function useGenerateMemo(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { title: string; sourceText: string; subject?: string; level?: string }) => {
      const { data, error } = await supabase.functions.invoke<{ sheet: MemoSheet; error?: string }>("tools-ai", {
        body: { action: "memo", ...payload },
      });
      if (error) throw error;
      if (!data?.sheet) throw new Error(data?.error ?? "Impossible de générer cette fiche.");
      return data.sheet;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tools", "memo-sheets", userId] }),
  });
}
