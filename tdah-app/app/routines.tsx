import { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, FlatList, Alert } from 'react-native';
import { Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../lib/supabase/AuthProvider';
import { spacing, fonts, radius, shadow, makeTypography, type ThemeColors } from '../constants/theme';
import { useTheme } from '../lib/theme/ThemeProvider';
import { listRoutines, createRoutine, toggleRoutine, deleteRoutine, type Routine } from '../lib/supabase/routines';

type MomentJournee = 'n_importe_quand' | 'matin' | 'jour' | 'soir';
const MOMENT_LABELS: Record<MomentJournee, string> = {
  n_importe_quand: 'N’importe quand',
  matin: 'Matin',
  jour: 'Jour',
  soir: 'Soir',
};
const MOMENTS: MomentJournee[] = ['n_importe_quand', 'matin', 'jour', 'soir'];
// Index alignés sur JS Date.getDay() : 0 = dimanche.
const JOURS: { label: string; value: number }[] = [
  { label: 'L', value: 1 },
  { label: 'M', value: 2 },
  { label: 'M', value: 3 },
  { label: 'J', value: 4 },
  { label: 'V', value: 5 },
  { label: 'S', value: 6 },
  { label: 'D', value: 0 },
];

export default function RoutinesScreen() {
  const { session } = useAuth();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [titre, setTitre] = useState('');
  const [moment, setMoment] = useState<MomentJournee>('n_importe_quand');
  const [estimation, setEstimation] = useState('');
  const [jours, setJours] = useState<number[]>([1, 2, 3, 4, 5, 6, 0]);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setRoutines(await listRoutines());
    } catch {
      Alert.alert('Erreur', 'Impossible de charger tes routines pour le moment.');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function toggleJour(value: number) {
    setJours((prev) => (prev.includes(value) ? prev.filter((j) => j !== value) : [...prev, value]));
  }

  async function submit() {
    if (!titre.trim() || !session || jours.length === 0) return;
    setSaving(true);
    try {
      await createRoutine(session.user.id, {
        titre: titre.trim(),
        moment_journee: moment,
        estimation_minutes: estimation ? parseInt(estimation, 10) || null : null,
        jours,
      });
      setTitre('');
      setEstimation('');
      await load();
    } catch {
      Alert.alert('Erreur', 'Impossible de créer cette routine.');
    } finally {
      setSaving(false);
    }
  }

  async function onToggle(r: Routine) {
    await toggleRoutine(r.id, !r.actif);
    load();
  }

  async function onDelete(r: Routine) {
    await deleteRoutine(r.id);
    load();
  }

  return (
    <View style={styles.container}>
      <Stack.Screen
        options={{
          headerShown: true,
          title: 'Routines',
          headerBackTitle: 'Retour',
          headerStyle: { backgroundColor: colors.surface },
          headerTintColor: colors.text,
        }}
      />
      <FlatList
        contentContainerStyle={{ padding: spacing.lg }}
        data={routines}
        keyExtractor={(r) => r.id}
        ListHeaderComponent={
          <>
            <Text style={styles.subtitle}>
              Une routine se reproduit toute seule les jours choisis — plus besoin de la re-taper chaque matin.
            </Text>

            <TextInput
              style={styles.input}
              placeholder="Ex : prendre mes médicaments"
              placeholderTextColor={colors.textMuted}
              value={titre}
              onChangeText={setTitre}
            />

            <Text style={styles.label}>Moment</Text>
            <View style={styles.chipRow}>
              {MOMENTS.map((m) => (
                <Pressable key={m} style={[styles.chip, moment === m && styles.chipActive]} onPress={() => setMoment(m)}>
                  <Text style={[styles.chipText, moment === m && styles.chipTextActive]}>{MOMENT_LABELS[m]}</Text>
                </Pressable>
              ))}
            </View>

            <Text style={styles.label}>Jours</Text>
            <View style={styles.chipRow}>
              {JOURS.map((j) => (
                <Pressable
                  key={j.value}
                  style={[styles.dayChip, jours.includes(j.value) && styles.chipActive]}
                  onPress={() => toggleJour(j.value)}
                >
                  <Text style={[styles.chipText, jours.includes(j.value) && styles.chipTextActive]}>{j.label}</Text>
                </Pressable>
              ))}
            </View>

            <TextInput
              style={[styles.input, { marginTop: spacing.md }]}
              placeholder="Estimation en minutes (optionnel)"
              placeholderTextColor={colors.textMuted}
              keyboardType="number-pad"
              value={estimation}
              onChangeText={setEstimation}
            />

            <Pressable style={styles.saveButton} onPress={submit} disabled={saving}>
              <Text style={styles.saveButtonText}>{saving ? 'Création...' : 'Créer la routine'}</Text>
            </Pressable>

            {routines.length > 0 && <Text style={styles.listTitle}>Tes routines</Text>}
          </>
        }
        renderItem={({ item }) => (
          <View style={[styles.routineCard, !item.actif && styles.routineCardInactive]}>
            <View style={{ flex: 1 }}>
              <Text style={styles.routineTitle}>{item.titre}</Text>
              <Text style={styles.caption}>
                {MOMENT_LABELS[item.moment_journee]} · {item.jours.length === 7 ? 'tous les jours' : `${item.jours.length} j/semaine`}
              </Text>
            </View>
            <Pressable hitSlop={10} onPress={() => onToggle(item)} style={{ marginRight: spacing.md }}>
              <Ionicons name={item.actif ? 'pause-circle-outline' : 'play-circle-outline'} size={24} color={colors.primary} />
            </Pressable>
            <Pressable hitSlop={12} onPress={() => onDelete(item)}>
              <Ionicons name="trash-outline" size={20} color={colors.warning} />
            </Pressable>
          </View>
        )}
      />
    </View>
  );
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    subtitle: { ...typography.body, color: colors.textMuted, marginBottom: spacing.md },
    label: { ...typography.caption, marginTop: spacing.md, marginBottom: spacing.xs },
    input: {
      backgroundColor: colors.surface,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.md,
      padding: spacing.md,
      fontSize: 15,
      fontFamily: fonts.regular,
      color: colors.text,
    },
    chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
    chip: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingVertical: spacing.xs, paddingHorizontal: spacing.md },
    dayChip: {
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: 18,
      width: 36,
      height: 36,
      alignItems: 'center',
      justifyContent: 'center',
    },
    chipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
    chipText: { color: colors.textMuted, fontSize: 13, fontFamily: fonts.medium },
    chipTextActive: { color: colors.primary, fontFamily: fonts.semibold },
    saveButton: { backgroundColor: colors.primary, borderRadius: radius.md, padding: spacing.md, alignItems: 'center', marginTop: spacing.lg, ...shadow.soft },
    saveButtonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 16 },
    listTitle: { ...typography.heading, fontSize: 16, marginTop: spacing.xl, marginBottom: spacing.sm },
    routineCard: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.surface,
      borderRadius: radius.md,
      padding: spacing.md,
      marginBottom: spacing.sm,
      ...shadow.soft,
    },
    routineCardInactive: { opacity: 0.5 },
    routineTitle: { ...typography.body, fontFamily: fonts.semibold },
    caption: { ...typography.caption, marginTop: 2 },
  });
}
