import { supabase } from '../supabase/client';

export async function generateGhostReply(userId: string, contexte: string): Promise<string> {
  const { data, error } = await supabase.rpc('generate_ghost_reply', {
    p_user_id: userId,
    p_contexte: contexte,
  });
  if (error) throw error;
  return data as string;
}
