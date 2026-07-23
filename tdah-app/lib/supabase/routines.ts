import { supabase } from './client';

type MomentJournee = 'n_importe_quand' | 'matin' | 'jour' | 'soir';

export type Routine = {
  id: string;
  titre: string;
  moment_journee: MomentJournee;
  estimation_minutes: number | null;
  jours: number[];
  actif: boolean;
};

export async function listRoutines(): Promise<Routine[]> {
  const { data, error } = await supabase
    .from('routines')
    .select('id, titre, moment_journee, estimation_minutes, jours, actif')
    .order('created_at', { ascending: true });
  if (error) throw error;
  return data ?? [];
}

export async function createRoutine(
  userId: string,
  routine: { titre: string; moment_journee: MomentJournee; estimation_minutes: number | null; jours: number[] }
) {
  const { error } = await supabase.from('routines').insert({ user_id: userId, ...routine });
  if (error) throw error;
}

export async function toggleRoutine(routineId: string, actif: boolean) {
  await supabase.from('routines').update({ actif }).eq('id', routineId);
}

export async function deleteRoutine(routineId: string) {
  await supabase.from('routines').delete().eq('id', routineId);
}

// Matérialise les routines actives du jour en vraies tâches, sans dupliquer
// si l'app est rouverte plusieurs fois dans la journée.
export async function ensureRoutinesForToday(userId: string) {
  const todayStr = new Date().toISOString().slice(0, 10);
  const weekday = new Date().getDay();

  const { data: routines } = await supabase
    .from('routines')
    .select('id, titre, moment_journee, estimation_minutes, jours')
    .eq('actif', true)
    .contains('jours', [weekday]);
  if (!routines || routines.length === 0) return;

  const { data: existing } = await supabase
    .from('tasks')
    .select('routine_id')
    .eq('date_prevue', todayStr)
    .not('routine_id', 'is', null);
  const existingIds = new Set((existing ?? []).map((t) => t.routine_id));

  const missing = routines.filter((r) => !existingIds.has(r.id));
  if (missing.length === 0) return;

  const rows = missing.map((r) => ({
    user_id: userId,
    titre: r.titre,
    moment_journee: r.moment_journee,
    estimation_minutes: r.estimation_minutes,
    date_prevue: todayStr,
    routine_id: r.id,
  }));
  await supabase.from('tasks').insert(rows);
}
