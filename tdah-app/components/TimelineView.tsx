import { View, Text, Pressable, ScrollView, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, typography, fonts } from '../constants/theme';
import { resolveTaskIcon } from '../lib/taskIcon';

// Vue frise horaire façon Tiimo : la vue liste reste la vue "détails" (édition,
// découpage IA, dread...), celle-ci sert de vue "coup d'œil" pour visualiser
// la charge de la journée dans l'espace, pas juste dans une liste verticale.

type MomentJournee = 'n_importe_quand' | 'matin' | 'jour' | 'soir';
type TimelineTask = {
  id: string;
  titre: string;
  statut: 'a_faire' | 'en_cours' | 'fait' | 'reporte';
  estimation_minutes: number | null;
  heure_debut: string | null;
  moment_journee: MomentJournee;
  icone_manuelle?: string | null;
  couleur_manuelle?: string | null;
};

const START_HOUR = 6;
const END_HOUR = 22;
const PX_PER_MIN = 1.1;
const HOUR_HEIGHT = 60 * PX_PER_MIN;
const MIN_BLOCK_HEIGHT = 32;
// En dessous de ce seuil, un trou est juste une marge normale entre deux
// tâches — pas la peine de le signaler, ça ajouterait du bruit visuel.
const MIN_GAP_MINUTES = 30;

function formatDuration(minutes: number) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h} h`;
  return `${h} h ${m}`;
}

const MOMENT_COLOR: Record<MomentJournee, string> = {
  matin: '#F0A860',
  jour: colors.primary,
  soir: '#8B6FD8',
  n_importe_quand: colors.textMuted,
};

function parseMinutes(heureDebut: string) {
  const [h, m] = heureDebut.split(':').map(Number);
  return h * 60 + m;
}

// Détection des trous dans la journée (plainte citée dans les avis Tiimo :
// aucune représentation visuelle des créneaux libres entre les tâches).
function computeGaps(placed: TimelineTask[]): { start: number; end: number }[] {
  const dayStart = START_HOUR * 60;
  const dayEnd = END_HOUR * 60;

  const intervals = placed
    .map((t): [number, number] => {
      const start = parseMinutes(t.heure_debut!);
      const duration = t.estimation_minutes ?? 30;
      return [Math.max(dayStart, start), Math.min(dayEnd, start + duration)];
    })
    .filter(([s, e]) => e > s)
    .sort((a, b) => a[0] - b[0]);

  const merged: [number, number][] = [];
  for (const [s, e] of intervals) {
    const last = merged[merged.length - 1];
    if (last && s <= last[1]) {
      last[1] = Math.max(last[1], e);
    } else {
      merged.push([s, e]);
    }
  }

  const gaps: { start: number; end: number }[] = [];
  let cursor = dayStart;
  for (const [s, e] of merged) {
    if (s - cursor >= MIN_GAP_MINUTES) gaps.push({ start: cursor, end: s });
    cursor = Math.max(cursor, e);
  }
  if (dayEnd - cursor >= MIN_GAP_MINUTES) gaps.push({ start: cursor, end: dayEnd });
  return gaps;
}

export function TimelineView({
  tasks,
  onToggleDone,
  onFocus,
}: {
  tasks: TimelineTask[];
  onToggleDone: (task: TimelineTask) => void;
  onFocus: (task: TimelineTask) => void;
}) {
  const placed = tasks.filter((t) => t.heure_debut);
  const sansHoraire = tasks.filter((t) => !t.heure_debut);
  const hours = Array.from({ length: END_HOUR - START_HOUR + 1 }, (_, i) => START_HOUR + i);
  const totalHeight = hours.length * HOUR_HEIGHT;
  const gaps = computeGaps(placed);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={{ paddingBottom: spacing.xl }}>
      <View style={[styles.grid, { height: totalHeight }]}>
        {hours.map((h) => (
          <View key={h} style={[styles.hourRow, { height: HOUR_HEIGHT }]}>
            <Text style={styles.hourLabel}>{String(h).padStart(2, '0')}:00</Text>
            <View style={styles.hourLine} />
          </View>
        ))}

        {gaps.map((gap) => {
          const top = (gap.start - START_HOUR * 60) * PX_PER_MIN;
          const height = (gap.end - gap.start) * PX_PER_MIN;
          return (
            <View key={`${gap.start}-${gap.end}`} style={[styles.gapBlock, { top, height }]}>
              <Text style={styles.gapText}>{formatDuration(gap.end - gap.start)} libres</Text>
            </View>
          );
        })}

        {placed.map((task) => {
          const startMin = Math.max(0, parseMinutes(task.heure_debut!) - START_HOUR * 60);
          const durationMin = task.estimation_minutes ?? 30;
          const top = startMin * PX_PER_MIN;
          const height = Math.max(MIN_BLOCK_HEIGHT, durationMin * PX_PER_MIN);
          const color = MOMENT_COLOR[task.moment_journee ?? 'n_importe_quand'];

          return (
            <Pressable
              key={task.id}
              style={[
                styles.block,
                { top, height, borderColor: color, backgroundColor: task.statut === 'fait' ? colors.surface : `${color}22` },
              ]}
              onPress={() => onToggleDone(task)}
            >
              <Text numberOfLines={2} style={[styles.blockText, task.statut === 'fait' && styles.blockTextDone]}>
                {task.statut === 'fait' ? '✓ ' : `${resolveTaskIcon(task).emoji} `}
                {task.titre}
              </Text>
              {task.statut !== 'fait' && (
                <Pressable hitSlop={6} onPress={() => onFocus(task)}>
                  <Ionicons name="play-circle-outline" size={16} color={color} />
                </Pressable>
              )}
            </Pressable>
          );
        })}
      </View>

      {sansHoraire.length > 0 && (
        <View style={styles.sansHoraireSection}>
          <Text style={styles.sansHoraireTitle}>Sans horaire fixe</Text>
          {sansHoraire.map((task) => (
            <Pressable key={task.id} style={styles.sansHoraireRow} onPress={() => onToggleDone(task)}>
              <Ionicons
                name={task.statut === 'fait' ? 'checkmark-circle' : 'ellipse-outline'}
                size={18}
                color={task.statut === 'fait' ? colors.success : colors.textMuted}
              />
              <Text style={[styles.sansHoraireText, task.statut === 'fait' && styles.blockTextDone]}>{task.titre}</Text>
            </Pressable>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1 },
  grid: { position: 'relative', marginLeft: spacing.sm },
  hourRow: { flexDirection: 'row', alignItems: 'flex-start' },
  hourLabel: { ...typography.caption, width: 44, fontSize: 11 },
  hourLine: { flex: 1, borderTopWidth: 1, borderTopColor: colors.border, marginTop: 6 },
  block: {
    position: 'absolute',
    left: 52,
    right: spacing.sm,
    borderRadius: 10,
    borderWidth: 1.5,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.xs,
  },
  blockText: { ...typography.body, fontSize: 13, fontFamily: fonts.semibold, flex: 1 },
  blockTextDone: { textDecorationLine: 'line-through', color: colors.textMuted },
  gapBlock: {
    position: 'absolute',
    left: 52,
    right: spacing.sm,
    borderRadius: 10,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  gapText: { ...typography.caption, fontSize: 11 },
  sansHoraireSection: { marginTop: spacing.lg, paddingHorizontal: spacing.sm },
  sansHoraireTitle: { ...typography.caption, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: spacing.xs, fontFamily: fonts.bold },
  sansHoraireRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.xs },
  sansHoraireText: { ...typography.body, fontSize: 14 },
});
