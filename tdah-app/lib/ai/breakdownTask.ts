import { supabase } from '../supabase/client';

// Appelle la fonction Postgres break_down_task (pg_net), pas une Edge
// Function — voir supabase/migrations/0003_ai_via_pg_net.sql. La clé
// Anthropic reste côté serveur (Supabase Vault), jamais exposée au client.
export async function breakdownTask(titre: string, preferenceTon: string, granularite: 1 | 2 | 3 = 2): Promise<string[]> {
  const { data, error } = await supabase.rpc('break_down_task', {
    p_titre: titre,
    p_preference_ton: preferenceTon,
    p_granularite: granularite,
  });

  if (error) throw error;
  return (data as { sous_taches: string[] }).sous_taches;
}
