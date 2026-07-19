import { supabase } from "@/lib/supabase/client";

export type CreateTaskPayload = {
  studentId: string;
  title: string;
  subject: string | null;
  chapter: string | null;
  level: string | null;
  dueAt: Date | null;
  estimatedMinutes: number;
  difficulty: number;
  notes: string | null;
  groupId: string | null;
  shareWithGroup: boolean;
  wantsReminder: boolean;
};

export async function createTask(payload: CreateTaskPayload): Promise<{ id: string }> {
  const { data, error } = await supabase
    .from("student_tasks")
    .insert({
      student_id: payload.studentId,
      title: payload.title.trim(),
      subject: payload.subject,
      chapter: payload.chapter,
      level: payload.level,
      due_at: payload.dueAt ? payload.dueAt.toISOString() : null,
      estimated_minutes: payload.estimatedMinutes,
      difficulty: payload.difficulty,
      notes: payload.notes,
      group_id: payload.shareWithGroup ? payload.groupId : null,
      share_with_group: payload.shareWithGroup && Boolean(payload.groupId),
      channels: payload.wantsReminder ? ["app"] : [],
      reminder_at: payload.wantsReminder && payload.dueAt ? new Date(payload.dueAt.getTime() - 60 * 60 * 1000).toISOString() : null,
      priority_score: payload.difficulty * 10 + (payload.dueAt ? 0 : -5),
      source_type: "manual",
      status: "todo",
    })
    .select("id")
    .single();
  if (error) throw error;
  return { id: data.id };
}

export async function markTaskDone(taskId: string, actualMinutes: number | null, selfGrade: number | null): Promise<void> {
  const { error } = await supabase
    .from("student_tasks")
    .update({ status: "done", completed_at: new Date().toISOString(), actual_minutes: actualMinutes, self_grade: selfGrade })
    .eq("id", taskId);
  if (error) throw error;
}

export async function reopenTask(taskId: string): Promise<void> {
  const { error } = await supabase.from("student_tasks").update({ status: "todo", completed_at: null }).eq("id", taskId);
  if (error) throw error;
}

export async function deleteTask(taskId: string): Promise<void> {
  const { error } = await supabase.from("student_tasks").delete().eq("id", taskId);
  if (error) throw error;
}
