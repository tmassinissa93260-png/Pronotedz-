import { useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { EduLesson } from "@/lib/queries/curriculum";

type PlanResponse = { lessons: EduLesson[] };
type ContentResponse = { lesson: EduLesson };

/** Chapter -> AI proposes its leçon breakdown (cached as edu_lessons rows). */
export function useGenerateLessonPlan(chapterId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await supabase.functions.invoke<PlanResponse>("curriculum-ai", {
        body: { action: "plan", chapterId },
      });
      if (error) throw error;
      if (!data) throw new Error("Réponse vide du générateur de plan.");
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["curriculum", "lessons", chapterId] });
    },
  });
}

/** Leçon -> AI writes the explanation, exercises and sujet (cached on the row). */
export function useGenerateLessonContent(lessonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (opts?: { simplify?: boolean }) => {
      const { data, error } = await supabase.functions.invoke<ContentResponse>("curriculum-ai", {
        body: { action: "content", lessonId, simplify: opts?.simplify ?? false },
      });
      if (error) throw error;
      if (!data) throw new Error("Réponse vide du générateur de leçon.");
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["curriculum", "lesson", lessonId] });
    },
  });
}
