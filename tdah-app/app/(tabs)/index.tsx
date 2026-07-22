import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  Pressable,
  SectionList,
  StyleSheet,
  ActivityIndicator,
  Alert,
  Modal,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { supabase } from '../../lib/supabase/client';
import { breakdownTask } from '../../lib/ai/breakdownTask';
import { planFromBraindump } from '../../lib/ai/braindump';
import { colors, spacing, typography } from '../../constants/theme';
import { useAuth } from '../../lib/supabase/AuthProvider';
import { useProfile } from '../../lib/supabase/useProfile';
import { bumpStreak } from '../../lib/supabase/streak';
import { maybeUnlockFirstTaskBadge } from '../../lib/supabase/badges';
import { useReward } from '../../lib/rewards/RewardProvider';
import { InteroceptionCheckIn } from '../../components/InteroceptionCheckIn';
import { syncTaskToCalendar } from '../../lib/calendar/sync';

type Subtask = { id: string; titre: string; fait: boolean; ordre: number };
type MomentJournee = 'n_importe_quand' | 'matin' | 'jour' | 'soir';
type Task = {
  id: string;
  titre: string;
  statut: 'a_faire' | 'en_cours' | 'fait' | 'reporte';
  estimation_minutes: number | null;
  temps_reel_minutes: number | null;
  moment_journee: MomentJournee;
  subtasks: Subtask[];
};

const today = () => new Date().toISOString().slice(0, 10);
const GRANULARITE_LABELS: Record<1 | 2 | 3, string> = { 1: 'Grandes lignes', 2: 'Standard', 3: 'Petits pas' };
const MOMENT_LABELS: Record<MomentJournee, string> = {
  n_importe_quand: 'N’importe quand',
  matin: 'Matin',
  jour: 'Jour',
  soir: 'Soir',
};
const MOMENT_ORDER: MomentJournee[] = ['n_importe_quand', 'matin', 'jour', 'soir'];

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
  const [braindumpVisible, setBraindumpVisible] = useState(false);
  const [braindumpText, setBraindumpText] = useState('');
  const [braindumpLoading, setBraindumpLoading] = useState(false);

  const loadTasks = useCallback(async () => {
    if (!session) return;
    setIsLoading(true);
    try {
      const { data, error } = await supabase
        .from('tasks')
        .select('id, titre, statut, estimation_minutes, temps_reel_minutes, moment_journee, subtasks(id, titre, fait, ordre)')
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

  // Regroupement par moment de journée (façon Tiimo) — moins de bruit qu'une
  // liste plate, un utilisateur voit tout de suite ce qui presse ce matin.
  const sections = useMemo(() => {
    return MOMENT_ORDER.map((moment) => ({
      title: MOMENT_LABELS[moment],
      data: tasks.filter((t) => (t.moment_journee ?? 'n_importe_quand') === moment),
    })).filter((s) => s.data.length > 0);
  }, [tasks]);

  async function submitBraindump() {
    if (!braindumpText.trim() || !session) return;
    setBraindumpLoading(true);
    try {
      const count = await planFromBraindump(session.user.id, braindumpText.trim());
      setBraindumpText('');
      setBraindumpVisible(false);
      await loadTasks();
      Alert.alert('Planning généré', `${count} tâche${count > 1 ? 's' : ''} ajoutée${count > 1 ? 's' : ''} à ta journée.`);
    } catch {
      Alert.alert('L’IA n’a pas pu générer ton planning', 'Réessaie dans un instant, ou ajoute tes tâches une par une.');
    } finally {
      setBraindumpLoading(false);
    }
  }

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

  async function addToCalendar(task: Task) {
    try {
      const ok = await syncTaskToCalendar({
        id: task.id,
        titre: task.titre,
        date_prevue: today(),
        estimation_minutes: task.estimation_minutes,
      });
      if (!ok) {
        Alert.alert('Permission refusée', 'Autorise l’accès au calendrier dans les réglages de ton téléphone pour utiliser cette fonction.');
        return;
      }
      Alert.alert('Ajouté', 'La tâche est maintenant dans ton calendrier.');
    } catch {
      Alert.alert('Erreur', 'Impossible d’ajouter cette tâche au calendrier pour le moment.');
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
      await maybeUnlockFirstTaskBadge(session.user.id);
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
      <View style={styles.headerRow}>
        <Text style={styles.title}>Aujourd’hui</Text>
        <Pressable style={styles.braindumpButton} onPress={() => setBraindumpVisible(true)}>
          <Ionicons name="chatbubble-ellipses-outline" size={16} color={colors.primary} />
          <Text style={styles.braindumpButtonText}>Vide-tête</Text>
        </Pressable>
      </View>
      {calibrationInsight && <Text style={styles.insight}>💡 {calibrationInsight}</Text>}

      <SectionList
        sections={sections}
        keyExtractor={(t) => t.id}
        stickySectionHeadersEnabled={false}
        contentContainerStyle={{ paddingBottom: spacing.xl }}
        ListEmptyComponent={
          <Text style={styles.empty}>Rien de prévu pour l’instant — ajoute une première tâche en bas, ou décris ta journée avec "Vide-tête".</Text>
        }
        renderSectionHeader={({ section }) => (
          <Text style={styles.sectionHeader}>
            {section.title} <Text style={styles.sectionCount}>({section.data.length})</Text>
          </Text>
        )}
        renderItem={({ item }) => (
          <View style={[styles.taskCard, item.statut === 'fait' && styles.taskCardDone]}>
            <View style={styles.taskHeader}>
              <Pressable style={styles.taskHeaderMain} onPress={() => markTaskDone(item)}>
                <Ionicons
                  name={item.statut === 'fait' ? 'checkmark-circle' : 'ellipse-outline'}
                  size={22}
                  color={item.statut === 'fait' ? colors.success : colors.textMuted}
                />
                <Text style={[styles.taskTitle, item.statut === 'fait' && styles.taskTitleDone]}>{item.titre}</Text>
              </Pressable>
              <Pressable hitSlop={8} onPress={() => addToCalendar(item)}>
                <Ionicons name="calendar-outline" size={18} color={colors.textMuted} />
              </Pressable>
            </View>

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

      <Modal visible={braindumpVisible} transparent animationType="slide" onRequestClose={() => setBraindumpVisible(false)}>
        <View style={styles.braindumpBackdrop}>
          <View style={styles.braindumpCard}>
            <Text style={styles.braindumpTitle}>Vide-tête</Text>
            <Text style={styles.braindumpSubtitle}>
              Décris tout ce que t'as à faire aujourd'hui, en vrac, comme ça vient — l'IA construit le planning pour toi.
            </Text>
            <TextInput
              style={styles.braindumpInput}
              multiline
              placeholder="Ex : je dois appeler maman, prendre mon petit déjeuner, aller au travail et récupérer les enfants cet après-midi..."
              placeholderTextColor={colors.textMuted}
              value={braindumpText}
              onChangeText={setBraindumpText}
              autoFocus
            />
            <View style={styles.braindumpActions}>
              <Pressable onPress={() => setBraindumpVisible(false)}>
                <Text style={styles.braindumpCancel}>Annuler</Text>
              </Pressable>
              <Pressable style={styles.braindumpSubmit} onPress={submitBraindump} disabled={braindumpLoading}>
                {braindumpLoading ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <Text style={styles.braindumpSubmitText}>Allez, c'est parti 🙌</Text>
                )}
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingHorizontal: spacing.lg, paddingTop: spacing.lg },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { ...typography.title, marginBottom: spacing.xs },
  braindumpButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.primaryMuted,
    borderRadius: 20,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
  },
  braindumpButtonText: { color: colors.primary, fontSize: 12, fontWeight: '600' },
  sectionHeader: { ...typography.caption, textTransform: 'uppercase', letterSpacing: 0.5, marginTop: spacing.md, marginBottom: spacing.xs, fontWeight: '700' },
  sectionCount: { fontWeight: '400', textTransform: 'none', letterSpacing: 0 },
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
  taskHeaderMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
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
  braindumpBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  braindumpCard: { backgroundColor: colors.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: spacing.lg, paddingBottom: spacing.xl },
  braindumpTitle: { ...typography.heading, marginBottom: spacing.xs },
  braindumpSubtitle: { ...typography.caption, marginBottom: spacing.md },
  braindumpInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: spacing.md,
    minHeight: 110,
    textAlignVertical: 'top',
    fontSize: 15,
    color: colors.text,
    backgroundColor: colors.background,
  },
  braindumpActions: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: spacing.md },
  braindumpCancel: { color: colors.textMuted, fontSize: 14 },
  braindumpSubmit: { backgroundColor: colors.primary, borderRadius: 20, paddingVertical: spacing.sm, paddingHorizontal: spacing.lg },
  braindumpSubmitText: { color: '#fff', fontWeight: '600', fontSize: 14 },
});
