import { useCallback, useEffect, useState } from 'react';
import { supabase } from '../supabase/client';
import { useAuth } from '../supabase/AuthProvider';
import { useSubscription } from './stripe';

// Limite mensuelle d'usage IA en gratuit — façon Tiimo, qui garde son
// générateur de sous-tâches et son Co-Planner accessibles en gratuit mais
// LIMITÉS plutôt que totalement bloqués (le blocage total d'une fonctionnalité
// déjà essayée est le vrai déclencheur de désinstalls/avis 1 étoile).
export const LIMITE_IA_GRATUITE = 5;

export async function recordAiUsage(userId: string): Promise<number> {
  const { data, error } = await supabase.rpc('record_ai_usage', { p_user_id: userId });
  if (error) throw error;
  return data as number;
}

export async function getAiUsage(userId: string): Promise<number> {
  const { data, error } = await supabase.rpc('get_ai_usage', { p_user_id: userId });
  if (error) throw error;
  return data as number;
}

// Compteur mensuel d'usage IA gratuit. Les utilisateurs premium ont un usage
// illimité — recordUsage() ne fait rien pour eux, pour ne jamais appeler le
// compteur serveur inutilement.
export function useAiQuota() {
  const { session } = useAuth();
  const { isPremium } = useSubscription();
  const [used, setUsed] = useState(0);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    if (!session) return;
    getAiUsage(session.user.id)
      .then(setUsed)
      .finally(() => setLoading(false));
  }, [session]);

  useEffect(() => {
    reload();
  }, [reload]);

  const remaining = Math.max(0, LIMITE_IA_GRATUITE - used);
  const canUse = isPremium || remaining > 0;

  async function recordUsage() {
    if (!session || isPremium) return;
    const compteur = await recordAiUsage(session.user.id);
    setUsed(compteur);
  }

  return { used, remaining, limit: LIMITE_IA_GRATUITE, isPremium, canUse, loading, recordUsage, reload };
}
