import { supabase } from "@/lib/supabase/client";

export type CreateGroupPayload = {
  ownerId: string;
  name: string;
  subject: string;
  level: string;
  description: string | null;
  maxMembers: number;
};

export async function createGroup(payload: CreateGroupPayload): Promise<{ id: string }> {
  const { data, error } = await supabase
    .from("study_groups")
    .insert({
      owner_id: payload.ownerId,
      name: payload.name.trim(),
      subject: payload.subject.trim(),
      level: payload.level.trim(),
      description: payload.description,
      max_members: payload.maxMembers,
      invite_code: "",
    })
    .select("id")
    .single();
  if (error) throw error;
  return { id: data.id };
}

export async function joinGroupByCode(code: string): Promise<{ groupId: string; groupName: string }> {
  const { data, error } = await supabase.rpc("join_group_by_code", { _code: code.trim() });
  if (error) throw new Error(error.message.includes("Code invalide") ? "Code invalide." : error.message);
  const row = data?.[0];
  if (!row) throw new Error("Code invalide.");
  return { groupId: row.group_id, groupName: row.group_name };
}

export async function leaveGroup(groupId: string, userId: string): Promise<void> {
  const { error } = await supabase.from("group_members").delete().eq("group_id", groupId).eq("user_id", userId);
  if (error) throw error;
}

export async function sendGroupMessage(groupId: string, authorId: string, body: string): Promise<void> {
  const { error } = await supabase.from("group_messages").insert({ group_id: groupId, author_id: authorId, body: body.trim() });
  if (error) throw error;
}

export async function createGroupEvent(groupId: string, createdBy: string, title: string, description: string | null, eventAt: Date): Promise<void> {
  const { error } = await supabase
    .from("group_events")
    .insert({ group_id: groupId, created_by: createdBy, title: title.trim(), description, event_at: eventAt.toISOString() });
  if (error) throw error;
}

export async function deleteGroupEvent(eventId: string): Promise<void> {
  const { error } = await supabase.from("group_events").delete().eq("id", eventId);
  if (error) throw error;
}

export async function uploadGroupResource(groupId: string, uploaderId: string, file: File, title: string): Promise<void> {
  const ext = file.name.split(".").pop()?.replace(/[^a-zA-Z0-9]/g, "") || "bin";
  const path = `${groupId}/${crypto.randomUUID()}.${ext}`;
  const { error: uploadError } = await supabase.storage.from("group-resources").upload(path, file);
  if (uploadError) throw uploadError;
  const { error } = await supabase.from("group_resources").insert({
    group_id: groupId,
    uploader_id: uploaderId,
    title: title.trim() || file.name,
    storage_path: path,
    mime_type: file.type || null,
    size_bytes: file.size,
  });
  if (error) throw error;
}

export async function deleteGroupResource(resourceId: string, storagePath: string): Promise<void> {
  await supabase.storage.from("group-resources").remove([storagePath]);
  const { error } = await supabase.from("group_resources").delete().eq("id", resourceId);
  if (error) throw error;
}

export async function startPomodoro(groupId: string, startedBy: string, phase: "focus" | "break", durationMin: number): Promise<void> {
  const startedAt = new Date();
  const endsAt = new Date(startedAt.getTime() + durationMin * 60_000);
  const { error } = await supabase.from("group_pomodoro_sessions").insert({
    group_id: groupId,
    started_by: startedBy,
    phase,
    started_at: startedAt.toISOString(),
    ends_at: endsAt.toISOString(),
  });
  if (error) throw error;
}

export type QuizQuestion = { question: string; options: string[]; correct_index: number; explanation: string };

export async function createGroupExamAlert(payload: {
  groupId: string;
  subject: string;
  chapters: string[];
  examDate: Date;
}): Promise<{ id: string; quiz: QuizQuestion[]; checklist: string[] }> {
  const { data, error } = await supabase.functions.invoke("group-quiz-ai", {
    body: {
      groupId: payload.groupId,
      subject: payload.subject,
      chapters: payload.chapters,
      examDate: payload.examDate.toISOString(),
    },
  });
  if (error) throw new Error(error.message ?? "Impossible de générer l'alerte examen.");
  if (data?.error) throw new Error(data.error);
  return data;
}

export async function deleteGroupExamAlert(id: string): Promise<void> {
  const { error } = await supabase.from("group_exam_alerts").delete().eq("id", id);
  if (error) throw error;
}
