import { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { supabase } from '../../lib/supabase/client';
import { useAuth } from '../../lib/supabase/AuthProvider';
import { colors, spacing, typography } from '../../constants/theme';
import { generatePatternInsight, type PatternInsight } from '../../lib/supabase/patternInsight';

// Volontairement PAS un pourcentage de tâches complétées : ce genre de métrique
// rejoue en permanence le sentiment d'échec chez les utilisateurs TDAH.
// On mesure plutôt 3 dimensions issues de la théorie de l'autodétermination :
// autonomie, compétence, connexion.

function startOfWeekISO() {
  const now = new Date();
  const day = now.getDay() || 7;
  const monday = new Date(now);
  monday.setDate(now.getDate() - day + 1);
  monday.setHours(0, 0, 0, 0);
  return monday.toISOString();
}

export default function DashboardScreen() {
  const { session } = useAuth();
  const [autonomie, setAutonomie] = useState(0);
  const [competence, setCompetence] = useState(0);
  const [connexion, setConnexion] = useState(0);
  const [streak, setStreak] = useState<{ jours_consecutifs: number; reparations_disponibles: number } | null>(null);
  const [insight, setInsight] = useState<PatternInsight | null>(null);
  const [insightLoading, setInsightLoading] = useState(false);

  async function loadInsight() {
    if (!session) return;
    setInsightLoading(true);
    try {
      const result = await generatePatternInsight(session.user.id);
      setInsight(result);
    } catch {
      setInsight(null);
    } finally {
      setInsightLoading(false);
    }
  }

  useEffect(() => {
    if (!session) return;
    const since = startOfWeekISO();
    loadInsight();

    supabase
      .from('tasks')
      .select('id', { count: 'exact', head: true })
      .eq('statut', 'fait')
      .gte('created_at', since)
      .then(({ count }) => setAutonomie(count ?? 0));

    supabase
      .from('tasks')
      .select('id, subtasks!inner(id)', { count: 'exact', head: true })
      .eq('statut', 'fait')
      .gte('created_at', since)
      .then(({ count }) => setCompetence(count ?? 0));

    supabase
      .from('sessions')
      .select('id', { count: 'exact', head: true })
      .gte('started_at', since)
      .then(({ count }) => setConnexion(count ?? 0));

    supabase
      .from('streaks')
      .select('jours_consecutifs, reparations_disponibles')
      .eq('user_id', session.user.id)
      .single()
      .then(({ data }) => setStreak(data));
  }, [session]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing.lg }}>
      <Text style={styles.title}>Ton bilan de la semaine</Text>
      <Text style={styles.subtitle}>Pas de note sur 100 ici — juste ce que tu as vraiment vécu.</Text>

      <View style={styles.insightCard}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.xs }}>
          <Ionicons name="sparkles-outline" size={18} color={colors.primary} />
          <Text style={styles.cardTitle}>Insight personnalisé</Text>
        </View>
        {insightLoading ? (
          <ActivityIndicator color={colors.primary} style={{ alignSelf: 'flex-start', marginTop: spacing.xs }} />
        ) : insight?.pret === true ? (
          <>
            <Text style={styles.insightPattern}>{insight.pattern}</Text>
            <Text style={styles.caption}>À essayer : {insight.suggestion}</Text>
          </>
        ) : (
          <Text style={styles.cardValue}>
            {insight?.pret === false ? insight.message : 'Utilise l’app pendant quelques semaines pour débloquer un premier insight basé sur tes vraies habitudes.'}
          </Text>
        )}
        {!insightLoading && (
          <Pressable onPress={loadInsight} style={{ marginTop: spacing.sm }}>
            <Text style={styles.refreshText}>Actualiser</Text>
          </Pressable>
        )}
      </View>

      <View style={styles.card}>
        <Ionicons name="compass-outline" size={24} color={colors.primary} />
        <View style={styles.cardText}>
          <Text style={styles.cardTitle}>Autonomie</Text>
          <Text style={styles.cardValue}>
            {autonomie === 0 ? 'Rien de finalisé pour l’instant, et c’est ok.' : `Tu as mené ${autonomie} tâche${autonomie > 1 ? 's' : ''} à ton rythme.`}
          </Text>
        </View>
      </View>

      <View style={styles.card}>
        <Ionicons name="ribbon-outline" size={24} color={colors.primary} />
        <View style={styles.cardText}>
          <Text style={styles.cardTitle}>Compétence</Text>
          <Text style={styles.cardValue}>
            {competence === 0 ? 'Pas encore de tâche complexe bouclée cette semaine.' : `Tu as géré ${competence} sujet${competence > 1 ? 's' : ''} qui demandait${competence > 1 ? 'ent' : ''} plusieurs étapes.`}
          </Text>
        </View>
      </View>

      <View style={styles.card}>
        <Ionicons name="people-outline" size={24} color={colors.primary} />
        <View style={styles.cardText}>
          <Text style={styles.cardTitle}>Connexion</Text>
          <Text style={styles.cardValue}>
            {connexion === 0 ? 'Aucune session focus cette semaine.' : `${connexion} session${connexion > 1 ? 's' : ''} de focus accompagné.`}
          </Text>
        </View>
      </View>

      {streak && (
        <View style={styles.streakCard}>
          <Text style={styles.streakText}>
            🔥 {streak.jours_consecutifs} jour{streak.jours_consecutifs > 1 ? 's' : ''} d’activité de suite
          </Text>
          <Text style={styles.caption}>
            {streak.reparations_disponibles} réparation{streak.reparations_disponibles > 1 ? 's' : ''} de série disponible{streak.reparations_disponibles > 1 ? 's' : ''} — un jour manqué ne remet pas tout à zéro.
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  title: { ...typography.title, marginBottom: spacing.xs },
  subtitle: { ...typography.body, color: colors.textMuted, marginBottom: spacing.lg },
  card: {
    flexDirection: 'row',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'flex-start',
  },
  cardText: { flex: 1 },
  cardTitle: { ...typography.heading, fontSize: 16, marginBottom: 2 },
  cardValue: { ...typography.body, color: colors.textMuted, fontSize: 14 },
  streakCard: { backgroundColor: colors.primaryMuted, borderRadius: 14, padding: spacing.md, marginTop: spacing.sm },
  streakText: { ...typography.body, fontWeight: '600' },
  caption: { ...typography.caption, marginTop: spacing.xs },
  insightCard: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing.md,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.primaryMuted,
  },
  insightPattern: { ...typography.body, fontWeight: '500' },
  refreshText: { color: colors.primary, fontSize: 13, fontWeight: '500' },
});
