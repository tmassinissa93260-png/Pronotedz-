import { supabase } from './client';

type MomentJournee = 'n_importe_quand' | 'matin' | 'jour' | 'soir';

export type MomentStats = Record<MomentJournee, { total: number; completed: number }>;

const EMPTY: MomentStats = {
  n_importe_quand: { total: 0, completed: 0 },
  matin: { total: 0, completed: 0 },
  jour: { total: 0, completed: 0 },
  soir: { total: 0, completed: 0 },
};

// Coach proactif : pas d'appel IA ici, juste une agrégation des tâches très
// angoissantes passées pour savoir à quel moment de la journée elles ont
// vraiment été menées à terme. Sert à avertir au moment de la création
// plutôt que de laisser l'utilisateur découvrir le pattern tout seul.
export async function getHighDreadMomentStats(userId: string): Promise<MomentStats> {
  const { data } = await supabase
    .from('tasks')
    .select('moment_journee, statut')
    .eq('user_id', userId)
    .gte('niveau_dread', 4)
    .lt('date_prevue', new Date().toISOString().slice(0, 10));

  const stats: MomentStats = {
    n_importe_quand: { total: 0, completed: 0 },
    matin: { total: 0, completed: 0 },
    jour: { total: 0, completed: 0 },
    soir: { total: 0, completed: 0 },
  };

  for (const row of data ?? []) {
    const moment = (row.moment_journee ?? 'n_importe_quand') as MomentJournee;
    if (!stats[moment]) continue;
    stats[moment].total += 1;
    if (row.statut === 'fait') stats[moment].completed += 1;
  }

  return data && data.length > 0 ? stats : EMPTY;
}
