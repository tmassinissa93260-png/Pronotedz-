import { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, SectionList, Alert } from 'react-native';
import { Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../lib/supabase/AuthProvider';
import { supabase } from '../lib/supabase/client';
import { spacing, fonts, radius, shadow, makeTypography, type ThemeColors } from '../constants/theme';
import { useTheme } from '../lib/theme/ThemeProvider';
import { resolveTaskIcon } from '../lib/taskIcon';

// Backlog façon Tiimo (liste de tâches "à placer" → glissées sur le calendrier).
// Un vrai glisser-déposer ne peut pas être vérifié fiablement depuis ce
// sandbox (tests web-only, aucun appareil tactile réel) : on obtient le même
// résultat — placer une tâche sans horaire sur le planning en un ou deux taps
// — avec un bouton "Maintenant" et un champ heure, sans risquer du code de
// geste non testé.

type PrioriteKey = 'haute' | 'moyenne' | 'basse' | 'aucune';
type Task = {
  id: string;
  titre: string;
  estimation_minutes: number | null;
  niveau_priorite: 'haute' | 'moyenne' | 'basse' | null;
  icone_manuelle: string | null;
  couleur_manuelle: string | null;
};

const PRIORITE_ORDER: PrioriteKey[] = ['haute', 'moyenne', 'basse', 'aucune'];
const PRIORITE_LABELS: Record<PrioriteKey, string> = {
  haute: 'Priorité haute',
  moyenne: 'Priorité moyenne',
  basse: 'Priorité basse',
  aucune: 'Sans priorité',
};

const today = () => new Date().toISOString().slice(0, 10);

function nextRoundedTime() {
  const d = new Date();
  const minutes = d.getMinutes();
  d.setMinutes(minutes + (5 - (minutes % 5)) % 5, 0, 0);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export default function BacklogScreen() {
  const { session } = useAuth();
  const { colors, focusMode } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [openTaskId, setOpenTaskId] = useState<string | null>(null);
  const [timeInput, setTimeInput] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    if (!session) return;
    setIsLoading(true);
    try {
      const { data, error } = await supabase
        .from('tasks')
        .select('id, titre, estimation_minutes, niveau_priorite, icone_manuelle, couleur_manuelle')
        .eq('date_prevue', today())
        .is('heure_debut', null)
        .neq('statut', 'fait')
        .order('created_at', { ascending: true });
      if (error) throw error;
      setTasks((data as Task[]) ?? []);
    } catch {
      Alert.alert('Connexion impossible', 'Impossible de charger le backlog pour le moment.');
    } finally {
      setIsLoading(false);
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  const sections = PRIORITE_ORDER.map((key) => ({
    key,
    title: PRIORITE_LABELS[key],
    data: tasks.filter((t) => (t.niveau_priorite ?? 'aucune') === key),
  })).filter((s) => s.data.length > 0);

  async function placeAt(taskId: string, hhmm: string) {
    if (!/^([01]\d|2[0-3]):([0-5]\d)$/.test(hhmm)) {
      Alert.alert('Format invalide', 'Utilise le format HH:MM, ex : 14:30.');
      return;
    }
    await supabase.from('tasks').update({ heure_debut: `${hhmm}:00` }).eq('id', taskId);
    setOpenTaskId(null);
    load();
  }

  async function placeNow(taskId: string) {
    await placeAt(taskId, nextRoundedTime());
  }

  return (
    <View style={styles.container}>
      <Stack.Screen
        options={{
          headerShown: true,
          title: 'Backlog',
          headerBackTitle: 'Retour',
          headerStyle: { backgroundColor: colors.surface },
          headerTintColor: colors.text,
        }}
      />
      <Text style={styles.subtitle}>
        Tes tâches sans horaire fixé aujourd'hui — place-les sur ton planning d'un tap, comme un glisser-déposer sans le geste.
      </Text>

      {!isLoading && tasks.length === 0 && (
        <Text style={styles.empty}>Rien en attente — toutes tes tâches du jour ont déjà un horaire.</Text>
      )}

      <SectionList
        contentContainerStyle={{ padding: spacing.lg, paddingTop: 0 }}
        sections={sections}
        keyExtractor={(t) => t.id}
        renderSectionHeader={({ section }) => <Text style={styles.sectionHeader}>{section.title}</Text>}
        renderItem={({ item }) => {
          const icon = resolveTaskIcon(item);
          const isOpen = openTaskId === item.id;
          return (
            <View style={styles.card}>
              <View style={styles.cardRow}>
                <View style={[styles.iconBubble, { backgroundColor: focusMode ? colors.surfaceAlt : icon.color }]}>
                  <Text style={styles.iconEmoji}>{icon.emoji}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.cardTitle}>{item.titre}</Text>
                  {item.estimation_minutes && <Text style={styles.caption}>{item.estimation_minutes} min</Text>}
                </View>
                <Pressable style={styles.nowButton} onPress={() => placeNow(item.id)}>
                  <Text style={styles.nowButtonText}>Maintenant</Text>
                </Pressable>
                <Pressable hitSlop={12} onPress={() => setOpenTaskId(isOpen ? null : item.id)}>
                  <Ionicons name={isOpen ? 'chevron-up' : 'time-outline'} size={20} color={colors.textMuted} />
                </Pressable>
              </View>
              {isOpen && (
                <View style={styles.timeRow}>
                  <TextInput
                    style={styles.timeInput}
                    placeholder="14:30"
                    placeholderTextColor={colors.textMuted}
                    value={timeInput[item.id] ?? ''}
                    onChangeText={(v) => setTimeInput((prev) => ({ ...prev, [item.id]: v }))}
                    onSubmitEditing={() => placeAt(item.id, timeInput[item.id] ?? '')}
                  />
                  <Pressable style={styles.placeButton} onPress={() => placeAt(item.id, timeInput[item.id] ?? '')}>
                    <Text style={styles.placeButtonText}>Placer</Text>
                  </Pressable>
                </View>
              )}
            </View>
          );
        }}
      />
    </View>
  );
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    subtitle: { ...typography.body, color: colors.textMuted, padding: spacing.lg, paddingBottom: spacing.sm },
    empty: { ...typography.body, color: colors.textMuted, paddingHorizontal: spacing.lg },
    sectionHeader: { ...typography.caption, textTransform: 'uppercase', letterSpacing: 0.5, fontFamily: fonts.bold, marginTop: spacing.md, marginBottom: spacing.xs },
    card: {
      backgroundColor: colors.surface,
      borderRadius: radius.md,
      padding: spacing.md,
      marginBottom: spacing.sm,
      ...shadow.soft,
    },
    cardRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    iconBubble: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center' },
    iconEmoji: { fontSize: 16 },
    cardTitle: { ...typography.body, fontFamily: fonts.semibold },
    caption: { ...typography.caption, marginTop: 2 },
    nowButton: { backgroundColor: colors.primaryMuted, borderRadius: radius.pill, paddingVertical: spacing.sm, paddingHorizontal: spacing.md, minHeight: 44, justifyContent: 'center' },
    nowButtonText: { color: colors.primary, fontSize: 12, fontFamily: fonts.semibold },
    timeRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
    timeInput: {
      flex: 1,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.sm,
      padding: spacing.sm,
      fontSize: 14,
      fontFamily: fonts.regular,
      color: colors.text,
    },
    placeButton: { backgroundColor: colors.primary, borderRadius: radius.sm, paddingVertical: spacing.sm, paddingHorizontal: spacing.md, justifyContent: 'center' },
    placeButtonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 13 },
  });
}
