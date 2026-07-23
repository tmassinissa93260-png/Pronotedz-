import { supabase } from './client';

export async function unlockBadge(userId: string, code: string) {
  await supabase.rpc('unlock_badge', { p_user_id: userId, p_code: code });
}

export async function maybeUnlockFirstTaskBadge(userId: string) {
  const { count } = await supabase
    .from('tasks')
    .select('id', { count: 'exact', head: true })
    .eq('statut', 'fait');
  if (count === 1) await unlockBadge(userId, 'premiere_tache');
}

export async function maybeUnlockTenSessionsBadge(userId: string) {
  const { count } = await supabase
    .from('sessions')
    .select('id', { count: 'exact', head: true })
    .not('ended_at', 'is', null);
  if (count === 10) await unlockBadge(userId, 'sessions_10');
}
