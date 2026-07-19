import { supabase } from "@/lib/supabase/client";

export async function pingStreak(userId: string): Promise<{ streakDays: number; lastPracticeDate: string } | null> {
  const { data, error } = await supabase.rpc("ping_streak", { _user: userId });
  if (error) throw error;
  const row = data?.[0];
  if (!row) return null;
  return { streakDays: row.streak_days, lastPracticeDate: row.last_practice_date };
}

export async function awardXp(userId: string, amount: number): Promise<number> {
  const { data, error } = await supabase.rpc("award_xp", { _user: userId, _amount: amount });
  if (error) throw error;
  return data ?? 0;
}

/** Marks a chapter as complete (idempotent) and awards a fixed XP amount the first time. */
export async function markChapterComplete(userId: string, chapterId: string): Promise<{ alreadyDone: boolean; xp: number }> {
  const { data: existing } = await supabase
    .from("gamification")
    .select("chapters_completed, xp")
    .eq("student_id", userId)
    .maybeSingle();

  const completed = Array.isArray(existing?.chapters_completed) ? (existing.chapters_completed as string[]) : [];
  if (completed.includes(chapterId)) {
    return { alreadyDone: true, xp: existing?.xp ?? 0 };
  }

  const { error } = await supabase
    .from("gamification")
    .upsert({ student_id: userId, chapters_completed: [...completed, chapterId] });
  if (error) throw error;

  const xp = await awardXp(userId, 20);
  return { alreadyDone: false, xp };
}
