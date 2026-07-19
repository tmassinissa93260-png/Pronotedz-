import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createTask, markTaskDone, reopenTask, deleteTask, type CreateTaskPayload } from "@/lib/tasks/actions";
import { awardXp } from "@/lib/gamification/actions";

export function useCreateTask(studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Omit<CreateTaskPayload, "studentId">) => createTask({ ...payload, studentId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks", "mine", studentId] }),
  });
}

export function useMarkTaskDone(studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ taskId, actualMinutes, selfGrade }: { taskId: string; actualMinutes: number | null; selfGrade: number | null }) => {
      await markTaskDone(taskId, actualMinutes, selfGrade);
      await awardXp(studentId, 5);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", "mine", studentId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", studentId] });
    },
  });
}

export function useReopenTask(studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => reopenTask(taskId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks", "mine", studentId] }),
  });
}

export function useDeleteTask(studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => deleteTask(taskId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks", "mine", studentId] }),
  });
}
