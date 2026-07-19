import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type StudyGroup = Database["public"]["Tables"]["study_groups"]["Row"];
export type GroupMember = Database["public"]["Tables"]["group_members"]["Row"];
export type GroupMessage = Database["public"]["Tables"]["group_messages"]["Row"];
export type GroupResource = Database["public"]["Tables"]["group_resources"]["Row"];
export type GroupEvent = Database["public"]["Tables"]["group_events"]["Row"];
export type GroupPomodoroSession = Database["public"]["Tables"]["group_pomodoro_sessions"]["Row"];
export type GroupExamAlert = Database["public"]["Tables"]["group_exam_alerts"]["Row"];
export type Profile = Database["public"]["Tables"]["profiles"]["Row"];

export type MyGroup = StudyGroup & { memberCount: number; myRole: string };

async function fetchMyGroups(userId: string): Promise<MyGroup[]> {
  const { data: memberships, error: memErr } = await supabase
    .from("group_members")
    .select("group_id, role")
    .eq("user_id", userId);
  if (memErr) throw memErr;
  const ids = (memberships ?? []).map((m) => m.group_id);
  if (!ids.length) return [];

  const [{ data: groups, error }, { data: counts }] = await Promise.all([
    supabase.from("study_groups").select("*").in("id", ids).order("created_at", { ascending: false }),
    supabase.from("group_members").select("group_id").in("group_id", ids),
  ]);
  if (error) throw error;

  const countMap = new Map<string, number>();
  for (const c of counts ?? []) countMap.set(c.group_id, (countMap.get(c.group_id) ?? 0) + 1);
  const roleMap = new Map((memberships ?? []).map((m) => [m.group_id, m.role]));

  return (groups ?? []).map((g) => ({ ...g, memberCount: countMap.get(g.id) ?? 0, myRole: roleMap.get(g.id) ?? "member" }));
}

export function myGroupsQueryOptions(userId: string | undefined) {
  return queryOptions({
    queryKey: ["groups", "mine", userId],
    queryFn: () => fetchMyGroups(userId as string),
    enabled: Boolean(userId),
    staleTime: 30_000,
  });
}

async function fetchGroup(groupId: string): Promise<StudyGroup | null> {
  const { data, error } = await supabase.from("study_groups").select("*").eq("id", groupId).maybeSingle();
  if (error) throw error;
  return data;
}

export function groupQueryOptions(groupId: string) {
  return queryOptions({
    queryKey: ["groups", "detail", groupId],
    queryFn: () => fetchGroup(groupId),
    staleTime: 30_000,
  });
}

export type GroupMemberWithProfile = GroupMember & { profile: Pick<Profile, "full_name" | "avatar_url"> | null };

async function fetchGroupMembers(groupId: string): Promise<GroupMemberWithProfile[]> {
  const { data, error } = await supabase
    .from("group_members")
    .select("*, profile:profiles(full_name, avatar_url)")
    .eq("group_id", groupId)
    .order("joined_at");
  if (error) throw error;
  return (data ?? []) as unknown as GroupMemberWithProfile[];
}

export function groupMembersQueryOptions(groupId: string) {
  return queryOptions({
    queryKey: ["groups", "members", groupId],
    queryFn: () => fetchGroupMembers(groupId),
    staleTime: 30_000,
  });
}

export type GroupMessageWithAuthor = GroupMessage & { author: Pick<Profile, "full_name" | "avatar_url"> | null };

async function fetchGroupMessages(groupId: string): Promise<GroupMessageWithAuthor[]> {
  const { data, error } = await supabase
    .from("group_messages")
    .select("*, author:profiles(full_name, avatar_url)")
    .eq("group_id", groupId)
    .order("created_at")
    .limit(200);
  if (error) throw error;
  return (data ?? []) as unknown as GroupMessageWithAuthor[];
}

export function groupMessagesQueryOptions(groupId: string) {
  return queryOptions({
    queryKey: ["groups", "messages", groupId],
    queryFn: () => fetchGroupMessages(groupId),
    staleTime: 5_000,
    refetchInterval: 8_000,
  });
}

async function fetchGroupResources(groupId: string): Promise<GroupResource[]> {
  const { data, error } = await supabase
    .from("group_resources")
    .select("*")
    .eq("group_id", groupId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data ?? [];
}

export function groupResourcesQueryOptions(groupId: string) {
  return queryOptions({
    queryKey: ["groups", "resources", groupId],
    queryFn: () => fetchGroupResources(groupId),
    staleTime: 30_000,
  });
}

async function fetchGroupEvents(groupId: string): Promise<GroupEvent[]> {
  const { data, error } = await supabase
    .from("group_events")
    .select("*")
    .eq("group_id", groupId)
    .order("event_at");
  if (error) throw error;
  return data ?? [];
}

export function groupEventsQueryOptions(groupId: string) {
  return queryOptions({
    queryKey: ["groups", "events", groupId],
    queryFn: () => fetchGroupEvents(groupId),
    staleTime: 30_000,
  });
}

async function fetchLatestPomodoro(groupId: string): Promise<GroupPomodoroSession | null> {
  const { data, error } = await supabase
    .from("group_pomodoro_sessions")
    .select("*")
    .eq("group_id", groupId)
    .order("started_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  return data;
}

export function groupPomodoroQueryOptions(groupId: string) {
  return queryOptions({
    queryKey: ["groups", "pomodoro", groupId],
    queryFn: () => fetchLatestPomodoro(groupId),
    staleTime: 5_000,
  });
}

async function fetchExamAlerts(groupId: string): Promise<GroupExamAlert[]> {
  const { data, error } = await supabase
    .from("group_exam_alerts")
    .select("*")
    .eq("group_id", groupId)
    .order("exam_date", { ascending: true });
  if (error) throw error;
  return data ?? [];
}

export function groupExamAlertsQueryOptions(groupId: string) {
  return queryOptions({
    queryKey: ["groups", "exam-alerts", groupId],
    queryFn: () => fetchExamAlerts(groupId),
    staleTime: 30_000,
  });
}
