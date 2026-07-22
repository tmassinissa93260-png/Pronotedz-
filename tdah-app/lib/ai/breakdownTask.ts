import { supabase } from '../supabase/client';

export async function breakdownTask(titre: string, preferenceTon: string, granularite: 1 | 2 | 3 = 2): Promise<string[]> {
  const { data, error } = await supabase.functions.invoke('ai-task-breakdown', {
    body: { titre, preferenceTon, granularite },
  });

  if (error) throw error;
  return data.sous_taches as string[];
}
