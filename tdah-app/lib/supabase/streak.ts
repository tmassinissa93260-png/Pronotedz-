import { supabase } from './client';

// À appeler à chaque engagement significatif (tâche finie, sous-tâche cochée,
// check-in répondu, session focus terminée) — pas seulement "journée complète".
export async function bumpStreak(userId: string) {
  const { data, error } = await supabase.rpc('update_streak', { p_user_id: userId });
  if (error) {
    console.warn('update_streak a échoué', error.message);
    return null;
  }
  return data?.[0] as { jours_consecutifs: number; reparation_utilisee: boolean } | undefined;
}
