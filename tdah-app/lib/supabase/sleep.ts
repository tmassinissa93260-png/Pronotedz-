import { supabase } from './client';

export type SleepEntry = {
  id: string;
  sommeil_minutes: number;
  sommeil_qualite: number;
  recorded_at: string;
};

// Saisie manuelle en V1 — la synchro Apple Watch/Health Connect nécessite un
// module natif incompatible avec Expo Go (comme la saisie vocale). La
// colonne `source` est déjà prête à recevoir 'apple_watch'/'oura'/'whoop'
// quand un build EAS sera fait : aucune migration supplémentaire à prévoir,
// juste un nouveau point d'entrée qui appellerait logSleep avec ces sources.
export async function logSleep(userId: string, coucher: string, leve: string, qualite: number) {
  const [ch, cm] = coucher.split(':').map(Number);
  const [lh, lm] = leve.split(':').map(Number);
  let minutes = lh * 60 + lm - (ch * 60 + cm);
  if (minutes <= 0) minutes += 24 * 60; // le réveil est le lendemain du coucher

  const { error } = await supabase.from('wearable_data').insert({
    user_id: userId,
    source: 'manuel',
    sommeil_minutes: minutes,
    sommeil_qualite: qualite,
  });
  if (error) throw error;
  return minutes;
}

export async function listRecentSleep(userId: string, days = 14): Promise<SleepEntry[]> {
  const since = new Date();
  since.setDate(since.getDate() - days);
  const { data, error } = await supabase
    .from('wearable_data')
    .select('id, sommeil_minutes, sommeil_qualite, recorded_at')
    .eq('user_id', userId)
    .gte('recorded_at', since.toISOString())
    .not('sommeil_minutes', 'is', null)
    .order('recorded_at', { ascending: false });
  if (error) throw error;
  return data ?? [];
}

export type SleepInsight = {
  bonSommeilTaux: number;
  mauvaisSommeilTaux: number;
  echantillonBon: number;
  echantillonMauvais: number;
};

const BON_SOMMEIL_MINUTES = 7 * 60;
const MIN_ECHANTILLON = 3;

// Corrélation sommeil/productivité — même logique que le coach proactif
// (agrégation pure, pas d'appel IA) : est-ce que les jours qui suivent une
// bonne nuit ont un meilleur taux de tâches terminées que les jours qui
// suivent une mauvaise nuit ?
export async function getSleepTaskCorrelation(userId: string): Promise<SleepInsight | null> {
  const sleep = await listRecentSleep(userId, 30);
  if (sleep.length < MIN_ECHANTILLON * 2) return null;

  const { data: tasks } = await supabase
    .from('tasks')
    .select('date_prevue, statut')
    .eq('user_id', userId)
    .gte('date_prevue', new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10));

  if (!tasks || tasks.length === 0) return null;

  const completionByDate = new Map<string, { done: number; total: number }>();
  for (const t of tasks) {
    const cur = completionByDate.get(t.date_prevue) ?? { done: 0, total: 0 };
    cur.total += 1;
    if (t.statut === 'fait') cur.done += 1;
    completionByDate.set(t.date_prevue, cur);
  }

  let bonDone = 0;
  let bonTotal = 0;
  let mauvaisDone = 0;
  let mauvaisTotal = 0;
  let echantillonBon = 0;
  let echantillonMauvais = 0;

  for (const entry of sleep) {
    // La nuit du recorded_at concerne la journée qui suit (on dort la nuit,
    // on agit le lendemain).
    const jourSuivant = new Date(entry.recorded_at);
    jourSuivant.setDate(jourSuivant.getDate() + 1);
    const jourStr = jourSuivant.toISOString().slice(0, 10);
    const stats = completionByDate.get(jourStr);
    if (!stats || stats.total === 0) continue;

    const bonneNuit = entry.sommeil_minutes >= BON_SOMMEIL_MINUTES || entry.sommeil_qualite >= 4;
    if (bonneNuit) {
      bonDone += stats.done;
      bonTotal += stats.total;
      echantillonBon += 1;
    } else {
      mauvaisDone += stats.done;
      mauvaisTotal += stats.total;
      echantillonMauvais += 1;
    }
  }

  if (echantillonBon < MIN_ECHANTILLON || echantillonMauvais < MIN_ECHANTILLON) return null;

  return {
    bonSommeilTaux: bonTotal > 0 ? bonDone / bonTotal : 0,
    mauvaisSommeilTaux: mauvaisTotal > 0 ? mauvaisDone / mauvaisTotal : 0,
    echantillonBon,
    echantillonMauvais,
  };
}
