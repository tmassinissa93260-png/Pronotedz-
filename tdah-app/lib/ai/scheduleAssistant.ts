import { supabase } from '../supabase/client';

export type ScheduleCommandTask = {
  id: string;
  titre: string;
  heure_debut: string | null;
  niveau_priorite: 'haute' | 'moyenne' | 'basse' | null;
  niveau_dread: number | null;
  statut: string;
};

export type ScheduleCommandResult = {
  action: 'decaler_tout' | 'reporter_tache' | 'prioriser' | 'repondre';
  minutes: number | null;
  tache_id: string | null;
  niveau_priorite: 'haute' | 'moyenne' | 'basse' | null;
  message: string;
};

export async function interpretScheduleCommand(
  userId: string,
  texte: string,
  taches: ScheduleCommandTask[]
): Promise<ScheduleCommandResult> {
  const { data, error } = await supabase.rpc('interpret_schedule_command', {
    p_user_id: userId,
    p_texte: texte,
    p_taches: taches,
  });
  if (error) throw error;
  return data as ScheduleCommandResult;
}
