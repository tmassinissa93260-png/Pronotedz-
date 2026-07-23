import { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, FlatList, Alert, Switch } from 'react-native';
import { Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../lib/supabase/AuthProvider';
import { spacing, fonts, radius, shadow, makeTypography, type ThemeColors } from '../constants/theme';
import { useTheme } from '../lib/theme/ThemeProvider';
import { logSleep, listRecentSleep, getSleepTaskCorrelation, type SleepEntry, type SleepInsight } from '../lib/supabase/sleep';
import { scheduleLightReminder, cancelLightReminder, isLightReminderScheduled } from '../lib/notifications';
import { PremiumScreen } from '../components/PremiumScreen';

function formatDuration(minutes: number) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m === 0 ? `${h} h` : `${h} h ${m}`;
}

export default function SommeilScreen() {
  const { session } = useAuth();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [coucher, setCoucher] = useState('23:00');
  const [leve, setLeve] = useState('07:00');
  const [qualite, setQualite] = useState(3);
  const [saving, setSaving] = useState(false);
  const [entries, setEntries] = useState<SleepEntry[]>([]);
  const [insight, setInsight] = useState<SleepInsight | null>(null);
  const [lightReminderOn, setLightReminderOn] = useState(false);

  const load = useCallback(async () => {
    if (!session) return;
    try {
      const [recent, corr] = await Promise.all([
        listRecentSleep(session.user.id),
        getSleepTaskCorrelation(session.user.id),
      ]);
      setEntries(recent);
      setInsight(corr);
    } catch {
      Alert.alert('Erreur', 'Impossible de charger ton historique de sommeil.');
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    isLightReminderScheduled().then(setLightReminderOn);
  }, []);

  // Rappel programmé ~15 min après l'heure de lever renseignée — la lumière
  // matinale est le complément naturel à la chronothérapie sommeil déjà ici,
  // les deux agissant sur le même axe circadien.
  async function toggleLightReminder(value: boolean) {
    if (value) {
      const [h, m] = leve.split(':').map(Number);
      if (Number.isNaN(h) || Number.isNaN(m)) {
        Alert.alert('Heure de lever invalide', 'Renseigne une heure de lever au format HH:MM avant d’activer ce rappel.');
        return;
      }
      const total = (h * 60 + m + 15 + 1440) % 1440;
      await scheduleLightReminder(Math.floor(total / 60), total % 60);
    } else {
      await cancelLightReminder();
    }
    setLightReminderOn(value);
  }

  async function submit() {
    if (!session) return;
    setSaving(true);
    try {
      await logSleep(session.user.id, coucher, leve, qualite);
      await load();
    } catch {
      Alert.alert('Format invalide', 'Utilise le format HH:MM pour les heures.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.container}>
      <Stack.Screen
        options={{
          headerShown: true,
          title: 'Sommeil',
          headerBackTitle: 'Retour',
          headerStyle: { backgroundColor: colors.surface },
          headerTintColor: colors.text,
        }}
      />
      <PremiumScreen label="Sommeil">
      <FlatList
        contentContainerStyle={{ padding: spacing.lg }}
        data={entries}
        keyExtractor={(e) => e.id}
        ListHeaderComponent={
          <>
            <Text style={styles.subtitle}>
              Saisie manuelle pour l'instant — la synchro automatique avec l'Apple Watch demandera un build de l'app, prévue plus tard.
            </Text>

            {insight && (
              <View style={styles.insightBox}>
                <Text style={styles.insightText}>
                  💤 Après une bonne nuit, tu termines {Math.round(insight.bonSommeilTaux * 100)}% de tes tâches, contre{' '}
                  {Math.round(insight.mauvaisSommeilTaux * 100)}% après une nuit courte ou difficile.
                </Text>
              </View>
            )}

            <View style={styles.timeRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.label}>Coucher</Text>
                <TextInput style={styles.input} value={coucher} onChangeText={setCoucher} placeholder="23:00" placeholderTextColor={colors.textMuted} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.label}>Lever</Text>
                <TextInput style={styles.input} value={leve} onChangeText={setLeve} placeholder="07:00" placeholderTextColor={colors.textMuted} />
              </View>
            </View>

            <View style={styles.lightReminderRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.lightReminderTitle}>☀️ Rappel lumière du matin</Text>
                <Text style={styles.caption}>
                  15 min après ton heure de lever — le levier le mieux prouvé pour recaler une horloge biologique en retard de phase.
                </Text>
              </View>
              <Switch
                value={lightReminderOn}
                onValueChange={toggleLightReminder}
                trackColor={{ false: colors.border, true: colors.primaryMuted }}
                thumbColor={lightReminderOn ? colors.primary : undefined}
              />
            </View>

            <Text style={styles.label}>Qualité ressentie</Text>
            <View style={styles.qualiteRow}>
              {([1, 2, 3, 4, 5] as const).map((n) => (
                <Pressable key={n} hitSlop={4} onPress={() => setQualite(n)}>
                  <Ionicons name={qualite >= n ? 'moon' : 'moon-outline'} size={22} color={qualite >= n ? colors.primary : colors.textMuted} />
                </Pressable>
              ))}
            </View>

            <Pressable style={styles.saveButton} onPress={submit} disabled={saving}>
              <Text style={styles.saveButtonText}>{saving ? 'Enregistrement...' : 'Enregistrer cette nuit'}</Text>
            </Pressable>

            {entries.length > 0 && <Text style={styles.listTitle}>Historique récent</Text>}
          </>
        }
        renderItem={({ item }) => (
          <View style={styles.entryRow}>
            <Text style={styles.entryDate}>
              {new Date(item.recorded_at).toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })}
            </Text>
            <Text style={styles.entryDuration}>{formatDuration(item.sommeil_minutes)}</Text>
            <View style={{ flexDirection: 'row' }}>
              {([1, 2, 3, 4, 5] as const).map((n) => (
                <Ionicons key={n} name={item.sommeil_qualite >= n ? 'moon' : 'moon-outline'} size={12} color={item.sommeil_qualite >= n ? colors.primary : colors.border} />
              ))}
            </View>
          </View>
        )}
      />
      </PremiumScreen>
    </View>
  );
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    subtitle: { ...typography.body, color: colors.textMuted, marginBottom: spacing.md },
    insightBox: { backgroundColor: colors.primaryMuted, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.md },
    insightText: { ...typography.caption, color: colors.primary, fontSize: 13 },
    timeRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
    lightReminderRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.md,
      backgroundColor: colors.surface,
      borderRadius: radius.md,
      padding: spacing.md,
      marginBottom: spacing.md,
      ...shadow.soft,
    },
    lightReminderTitle: { ...typography.body, fontFamily: fonts.semibold, marginBottom: 2 },
    caption: { ...typography.caption },
    label: { ...typography.caption, marginBottom: spacing.xs },
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
    qualiteRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.lg },
    saveButton: { backgroundColor: colors.primary, borderRadius: radius.md, padding: spacing.md, alignItems: 'center', ...shadow.soft },
    saveButtonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 16 },
    listTitle: { ...typography.heading, fontSize: 16, marginTop: spacing.xl, marginBottom: spacing.sm },
    entryRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      backgroundColor: colors.surface,
      borderRadius: radius.md,
      padding: spacing.md,
      marginBottom: spacing.sm,
      ...shadow.soft,
    },
    entryDate: { ...typography.body, fontSize: 14, fontFamily: fonts.semibold, flex: 1 },
    entryDuration: { ...typography.caption, marginRight: spacing.md },
  });
}
