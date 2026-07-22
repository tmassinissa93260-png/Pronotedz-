import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  Pressable,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { supabase } from '../../lib/supabase/client';
import { breakdownTask } from '../../lib/ai/breakdownTask';
import { colors, spacing, typography } from '../../constants/theme';
import { useAuth } from '../../lib/supabase/AuthProvider';
import { useProfile } from '../../lib/supabase/useProfile';
import { bumpStreak } from '../../lib/supabase/streak';
import { useReward } from '../../lib/rewards/RewardProvider';
import { InteroceptionCheckIn } from '../../components/InteroceptionCheckIn';

type Subtask = { id: string; titre: string; fait: boolean; ordre: number };
type Task = {
  id: string;
  titre: string;
  statut: 'a_faire' | 'en_cours' | 'fait' | 'reporte';
  estimation_minutes: number | null;
  temps_reel_minutes: number | null;
  subtasks: Subtask[];
};

const today = () => new Date().toISOString().slice(0, 10);
const GRANULARITE_LABELS: Record<1 | 2 | 3, string> = { 1: 'Grandes lignes', 2: 'Standard', 3: 'Petits pas' };

export default function AccueilScreen() {
  const { session } = useAuth();
  const profile = useProfile();
  const { celebrate } = useReward();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newTitle, setNewTitle] = useState('');
  const [estimationInput, setEstimationInput] = useState<Record<string, string>>({});
  const [decomposingId, setDecomposingId] = useState<string | null>(null);
  const [granulariteByTask, setGranulariteByTask] = useState<Record<string, 1 | 2 | 3>>({});
  const [checkInVisible, setCheckInVisible] = useState(false);
  const [openedAt] = useState(Date.now());

  const loadTasks = useCallback(async () => {
    if (!session) return;
    setIsLoading(true);
    try {
      const { data, error } = await supabase
        .from('tasks')
        .select('id, titre, statut, estimation_minutes, temps_reel_minutes, subtasks(id, titre, fait, ordre)')
        .eq('date_prevue', today())
        .order('created_at', { ascending: true });

      if (error) throw error;
      setTasks((data as unknown as Task[]) ?? []);
    } catch (e) {
      // Connexion instable ou requête en échec : on ne bloque jamais l'écran
      // sur un spinner infini, l'utilisateur garde au moins l'écran vide/précédent.
      Alert.alert('Connexion impossible', 'Impossible de charger tes tâches pour le moment. Réessaie dans un instant.');
    } finally {
      setIsLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // Check-in d'interoception discret après un long moment passé sur l'écran
  // du planning (proxy simple pour "session de travail prolongée" en V1 —
  // sera affiné en V2 avec la détection de surcharge par wearable).
  useEffect(() => {
    const timer = setTimeout(() => setCheckInVisible(true), 90 * 60 * 1000);
    return () => clearTimeout(timer);
  }, [openedAt]);

  // Calibration temporelle active : moyenne des écarts estimation/réel sur
  // les tâches déjà closes, pour donner un vrai insight, pas juste stocker.
  const calibrationInsight = useMemo(() => {
    const withBoth = tasks.filter((t) => t.estimation_minutes && t.temps_reel_minutes);
    if (withBoth.length < 3) return null;
    const ratio =
      withBoth.reduce((sum, t) => sum + t.temps_reel_minutes! / t.estimation_minutes!, 0) / withBoth.length;
    if (ratio < 1.15) return null; // pas d'écart notable, pas besoin de le dire
    return `Tu mets en moyenne ${ratio.toFixed(1)}x plus de temps que prévu — pense à multiplier tes estimations.`;
  }, [tasks]);

  async function addTask() {
    if (!newTitle.trim() || !session) return;
    const { error } = await supabase.from('tasks').insert({
      user_id: session.user.id,
      titre: newTitle.trim(),
      date_prevue: today(),
    });
    if (error) {
      Alert.alert('Erreur', error.message);
      return;
    }
    setNewTitle('');
    loadTasks();
  }

  async function saveEstimation(taskId: string) {
    const value = parseInt(estimationInput[taskId] ?? '', 10);
    if (!value || Number.isNaN(value)) return;
    await supabase.from('tasks').update({ estimation_minutes: value, statut: 'en_cours' }).eq('id', taskId);
    loadTasks();
  }

  async function decompose(taskId: string, titre: string) {
    setDecomposingId(taskId);
    try {
      const granularite = granulariteByTask[taskId] ?? 2;
      const sousTaches = await breakdownTask(titre, profile?.preference_ton ?? 'doux', granularite);
      const rows = sousTaches.map((titre, ordre) => ({ task_id: taskId, titre, ordre }));
      await supabase.from('subtasks').insert(rows);
      await loadTasks();
    } catch {
      Alert.alert('L’IA n’a pas pu découper la tâche', 'Réessaie dans un instant.');
    } finally {
      setDecomposingId(null);
    }
  }

  async function toggleSubtask(subtask: Subtask) {
    const nowFait = !subtask.fait;
    await supabase.from('subtasks').update({ fait: nowFait }).eq('id', subtask.id);
    if (nowFait && session) {
      await bumpStreak(session.user.id);
      celebrate(profile?.preference_gamification ?? 'discrete');
    }
    loadTasks();
  }

  async function completeTask(task: Task, tempsReel?: number) {
    await supabase
      .from('tasks')
      .update({ statut: 'fait', temps_reel_minutes: tempsReel ?? task.temps_reel_minutes })
      .eq('id', task.id);
    if (session) {
      await bumpStreak(session.user.id);
      celebrate(profile?.preference_gamification ?? 'discrete');
    }
    loadTasks();
  }

  function markTaskDone(task: Task) {
    if (task.statut === 'fait') return;

    if (task.estimation_minutes && !task.temps_reel_minutes && Platform.OS === 'ios' && Alert.prompt) {
      Alert.prompt(
        'Combien de temps ça t’a pris ?',
        `Tu avais estimé ${task.estimation_minutes} min.`,
        (value) => {
          const minutes = parseInt(value ?? '', 10);
          completeTask(task, Number.isNaN(minutes) ? undefined : minutes);
        },
        'plain-text',
        String(task.estimation_minutes)
      );
      return;
    }
    completeTask(task);
  }

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Text style={styles.title}>Aujourd’hui</Text>
      {calibrationInsight && <Text style={styles.insight}>💡 {calibrationInsight}</Text>}

      <FlatList
        data={tasks}
        keyExtractor={(t) => t.id}
        contentContainerStyle={{ paddingBottom: spacing.xl }}
        ListEmptyComponent={
          <Text style={styles.empty}>Rien de prévu pour l’instant — ajoute une première tâche en bas.</Text>
        }
        renderItem={({ item }) => (
          <View style={[styles.taskCard, item.statut === 'fait' && styles.taskCardDone]}>
            <Pressable style={styles.taskHeader} onPress={() => markTaskDone(item)}>
              <Ionicons
                name={item.statut === 'fait' ? 'checkmark-circle' : 'ellipse-outline'}
                size={22}
                color={item.statut === 'fait' ? colors.success : colors.textMuted}
              />
              <Text style={[styles.taskTitle, item.statut === 'fait' && styles.taskTitleDone]}>{item.titre}</Text>
            </Pressable>

            {item.estimation_minutes && (
              <Text style={styles.caption}>
                Estimé {item.estimation_minutes} min
                {item.temps_reel_minutes ? ` · réel ${item.temps_reel_minutes} min` : ''}
              </Text>
            )}

            {!item.estimation_minutes && item.statut !== 'fait' && (
              <View style={styles.estimationRow}>
                <TextInput
                  style={styles.estimationInput}
                  placeholder="Estimation (min)"
                  placeholderTextColor={colors.textMuted}
                  keyboardType="number-pad"
                  value={estimationInput[item.id] ?? ''}
                  onChangeText={(v) => setEstimationInput((prev) => ({ ...prev, [item.id]: v }))}
                  onSubmitEditing={() => saveEstimation(item.id)}
                />
              </View>
            )}

            {item.subtasks?.length > 0 ? (
              item.subtasks
                .sort((a, b) => a.ordre - b.ordre)
                .map((s) => (
                  <Pressable key={s.id} style={styles.subtaskRow} onPress={() => toggleSubtask(s)}>
                    <Ionicons
                      name={s.fait ? 'checkbox' : 'square-outline'}
                      size={18}
                      color={s.fait ? colors.success : colors.textMuted}
                    />
                    <Text style={[styles.subtaskText, s.fait && styles.taskTitleDone]}>{s.titre}</Text>
                  </Pressable>
                ))
            ) : (
              <View>
                <View style={styles.granulariteRow}>
                  {([1, 2, 3] as const).map((g) => (
                    <Pressable
                      key={g}
                      style={[
                        styles.granulariteChip,
                        (granulariteByTask[item.id] ?? 2) === g && styles.granulariteChipActive,
                      ]}
                      onPress={() => setGranulariteByTask((prev) => ({ ...prev, [item.id]: g }))}
                    >
                      <Text
                        style={[
                          styles.granulariteText,
                          (granulariteByTask[item.id] ?? 2) === g && styles.granulariteTextActive,
                        ]}
                      >
                        {GRANULARITE_LABELS[g]}
                      </Text>
                    </Pressable>
                  ))}
                </View>
                <Pressable
                  style={styles.decomposeButton}
                  onPress={() => decompose(item.id, item.titre)}
                  disabled={decomposingId === item.id}
                >
                  {decomposingId === item.id ? (
                    <ActivityIndicator size="small" color={colors.primary} />
                  ) : (
                    <>
                      <Ionicons name="sparkles-outline" size={16} color={colors.primary} />
                      <Text style={styles.decomposeText}>Découper avec l’IA</Text>
                    </>
                  )}
                </Pressable>
              </View>
            )}
          </View>
        )}
      />

      <View style={styles.addRow}>
        <TextInput
          style={styles.addInput}
          placeholder="Ajouter une tâche..."
          placeholderTextColor={colors.textMuted}
          value={newTitle}
          onChangeText={setNewTitle}
          onSubmitEditing={addTask}
        />
        <Pressable style={styles.addButton} onPress={addTask}>
          <Ionicons name="add" size={24} color="#fff" />
        </Pressable>
      </View>

      <InteroceptionCheckIn
        visible={checkInVisible}
        contexteDeclencheur="session_prolongee_planning"
        gamificationPref={profile?.preference_gamification ?? 'discrete'}
        onClose={() => setCheckInVisible(false)}
      />
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingHorizontal: spacing.lg, paddingTop: spacing.lg },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background },
  title: { ...typography.title, marginBottom: spacing.xs },
  insight: { ...typography.caption, backgroundColor: colors.primaryMuted, padding: spacing.sm, borderRadius: 10, marginBottom: spacing.md, color: colors.primary },
  empty: { ...typography.body, color: colors.textMuted, marginTop: spacing.lg },
  caption: { ...typography.caption, marginTop: spacing.xs },
  taskCard: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  taskCardDone: { opacity: 0.6 },
  taskHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  taskTitle: { ...typography.body, fontWeight: '600', flex: 1 },
  taskTitleDone: { textDecorationLine: 'line-through', color: colors.textMuted },
  estimationRow: { marginTop: spacing.sm },
  estimationInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: spacing.sm,
    fontSize: 14,
    color: colors.text,
  },
  subtaskRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.sm, marginLeft: spacing.lg },
  subtaskText: { ...typography.body, fontSize: 14, flex: 1 },
  granulariteRow: { flexDirection: 'row', gap: spacing.xs, marginTop: spacing.sm },
  granulariteChip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 20,
    paddingVertical: 4,
    paddingHorizontal: spacing.sm,
  },
  granulariteChipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
  granulariteText: { fontSize: 12, color: colors.textMuted },
  granulariteTextActive: { color: colors.primary, fontWeight: '600' },
  decomposeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.sm,
    alignSelf: 'flex-start',
  },
  decomposeText: { color: colors.primary, fontSize: 14, fontWeight: '500' },
  addRow: { flexDirection: 'row', gap: spacing.sm, paddingVertical: spacing.md },
  addInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: spacing.md,
    fontSize: 16,
    color: colors.text,
  },
  addButton: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
