import { supabase } from './client';

export type PatternInsight =
  | { pret: false; message: string }
  | { pret: true; pattern: string; confiance: number; suggestion: string };

export async function generatePatternInsight(userId: string): Promise<PatternInsight> {
  const { data, error } = await supabase.rpc('generate_pattern_insight', { p_user_id: userId });
  if (error) throw error;
  return data as PatternInsight;
}
