import { supabase } from '../supabase/client';

export async function breakdownTask(titre: string, preferenceTon: string): Promise<string[]> {
  const { data, error } = await supabase.functions.invoke('ai-task-breakdown', {
    body: { titre, preferenceTon },
  });

  if (error) throw error;
  return data.sous_taches as string[];
}
