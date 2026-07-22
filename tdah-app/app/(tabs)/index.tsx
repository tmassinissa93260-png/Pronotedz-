import { useCallback, useEffect, useState } from 'react';
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

export default function AccueilScreen() {
  const { session } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newTitle, setNewTitle] = useState('');
  const [estimationInput, setEstimationInput] = useState<Record<string, string>>({});
  const [decomposingId, setDecomposingId] = useState<string | null>(null);
  const [preferenceTon, setPreferenceTon] = useState('doux');

  const loadTasks = useCallback(async () => {
    if (!session) return;
    setIsLoading(true);

    const { data: profile } = await supabase
      .from('profiles')
      .select('preference_ton')
      .eq('id', session.user.id)
      .single();
    if (profile?.preference_ton) setPreferenceTon(profile.preference_ton);

    const { data, error } = await supabase
      .from('tasks')
      .select('id, titre, statut, estimation_minutes, temps_reel_minutes, subtasks(id, titre, fait, ordre)')
      .eq('date_prevue', today())
      .order('created_at', { ascending: true });

    if (error) {
      Alert.alert('Erreur', error.message);
    } else {
      setTasks((data as unknown as Task[]) ?? []);
    }
    setIsLoading(false);
  }, [session]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

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
      const sousTaches = await breakdownTask(titre, preferenceTon);
      const rows = sousTaches.map((titre, ordre) => ({ task_id: taskId, titre, ordre }));
      await supabase.from('subtasks').insert(rows);
      await loadTasks();
    } catch (e) {
      Alert.alert('L’IA n’a pas pu découper la tâche', 'Réessaie dans un instant.');
    } finally {
      setDecomposingId(null);
    }
  }

  async function toggleSubtask(subtask: Subtask) {
    await supabase.from('subtasks').update({ fait: !subtask.fait }).eq('id', subtask.id);
    loadTasks();
  }

  async function markTaskDone(task: Task) {
    // Calibration temporelle active : si une estimation existait, on compare
    // à ce que l'utilisateur rapporte comme temps réel avant de clore la tâche.
    if (task.estimation_minutes && !task.temps_reel_minutes) {
      Alert.prompt?.(
        'Combien de temps ça t’a pris ?',
        `Tu avais estimé ${task.estimation_minutes} min.`,
        async (value) => {
          const minutes = parseInt(value ?? '', 10);
          await supabase
            .from('tasks')
            .update({ statut: 'fait', temps_reel_minutes: Number.isNaN(minutes) ? null : minutes })
            .eq('id', task.id);
          loadTasks();
        },
        'plain-text',
        String(task.estimation_minutes)
      );
      // Alert.prompt n'existe que sur iOS — repli simple sur Android/web.
      if (Platform.OS !== 'ios') {
        await supabase.from('tasks').update({ statut: 'fait' }).eq('id', task.id);
        loadTasks();
      }
      return;
    }
    await supabase.from('tasks').update({ statut: 'fait' }).eq('id', task.id);
    loadTasks();
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
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingHorizontal: spacing.lg, paddingTop: spacing.lg },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background },
  title: { ...typography.title, marginBottom: spacing.md },
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
