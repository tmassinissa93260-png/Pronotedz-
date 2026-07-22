import { supabase } from '../supabase/client';

export async function planFromBraindump(userId: string, texte: string): Promise<number> {
  const { data, error } = await supabase.rpc('plan_from_braindump', { p_user_id: userId, p_texte: texte });
  if (error) throw error;
  return (data as { taches_creees: number }).taches_creees;
}
