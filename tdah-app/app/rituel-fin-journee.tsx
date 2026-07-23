import { useEffect, useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, ScrollView, Alert } from 'react-native';
import { Stack, useRouter } from 'expo-router';
import { supabase } from '../lib/supabase/client';
import { useAuth } from '../lib/supabase/AuthProvider';
import { colors, spacing, typography, fonts } from '../constants/theme';

// Rituel de clôture façon Sunsama : 3 questions courtes pour fermer la
// journée consciemment plutôt que de la laisser juste s'arrêter en carafe
// avec une liste de tâches non finies qui culpabilise le lendemain.

const today = () => new Date().toISOString().slice(0, 10);

type TacheNonFinie = { id: string; titre: string };

export default function RituelFinJourneeScreen() {
  const { session } = useAuth();
  const router = useRouter();
  const [accompli, setAccompli] = useState('');
  const [basculeDemain, setBasculeDemain] = useState('');
  const [ressenti, setRessenti] = useState('');
  const [saving, setSaving] = useState(false);
  const [dejaFait, setDejaFait] = useState(false);
  const [tachesNonFinies, setTachesNonFinies] = useState<TacheNonFinie[]>([]);
  const [reporting, setReporting] = useState(false);

  useEffect(() => {
    if (!session) return;
    supabase
      .from('daily_reviews')
      .select('accompli, bascule_demain, ressenti')
      .eq('date_jour', today())
      .maybeSingle()
      .then(({ data }) => {
        if (data) {
          setAccompli(data.accompli ?? '');
          setBasculeDemain(data.bascule_demain ?? '');
          setRessenti(data.ressenti ?? '');
          setDejaFait(true);
        }
      });

    supabase
      .from('tasks')
      .select('id, titre')
      .eq('date_prevue', today())
      .in('statut', ['a_faire', 'en_cours'])
      .then(({ data }) => setTachesNonFinies(data ?? []));
  }, [session]);

  // Report groupé façon "Too Hard Right Now" (Focus One) : aucune trace de
  // retard ne reste sur la tâche, elle change juste de date. Répond à la
  // plainte la plus citée dans les avis Tiimo/Sunsama sur la gestion des
  // tâches non finies en fin de journée.
  async function reporterTout() {
    if (tachesNonFinies.length === 0) return;
    setReporting(true);
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    await supabase
      .from('tasks')
      .update({ date_prevue: tomorrow.toISOString().slice(0, 10) })
      .in('id', tachesNonFinies.map((t) => t.id));
    setTachesNonFinies([]);
    setReporting(false);
  }

  async function save() {
    if (!session) return;
    setSaving(true);
    const { error } = await supabase.from('daily_reviews').upsert(
      {
        user_id: session.user.id,
        date_jour: today(),
        accompli: accompli.trim(),
        bascule_demain: basculeDemain.trim(),
        ressenti: ressenti.trim(),
      },
      { onConflict: 'user_id,date_jour' }
    );
    setSaving(false);
    if (error) {
      Alert.alert('Erreur', error.message);
      return;
    }
    router.back();
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xl }}>
      <Stack.Screen options={{ headerShown: true, title: 'Fin de journée', headerBackTitle: 'Retour' }} />

      <Text style={styles.subtitle}>
        {dejaFait
          ? 'Tu peux revenir sur tes réponses du jour.'
          : 'Trois questions, pas plus, pour fermer la journée sans la laisser en suspens dans ta tête.'}
      </Text>

      <Text style={styles.label}>Qu'est-ce que tu as accompli aujourd'hui ?</Text>
      <TextInput
        style={styles.textarea}
        multiline
        placeholder="Même une petite chose compte..."
        placeholderTextColor={colors.textMuted}
        value={accompli}
        onChangeText={setAccompli}
      />

      {tachesNonFinies.length > 0 && (
        <View style={styles.rolloverCard}>
          <Text style={styles.rolloverTitle}>
            {tachesNonFinies.length} tâche{tachesNonFinies.length > 1 ? 's' : ''} pas finie{tachesNonFinies.length > 1 ? 's' : ''} aujourd'hui
          </Text>
          <Text style={styles.rolloverSubtitle}>Ce n'est pas grave — elles peuvent juste glisser à demain, sans rien garder de "en retard".</Text>
          {tachesNonFinies.map((t) => (
            <Text key={t.id} style={styles.rolloverTask}>• {t.titre}</Text>
          ))}
          <Pressable style={styles.rolloverButton} onPress={reporterTout} disabled={reporting}>
            <Text style={styles.rolloverButtonText}>{reporting ? 'Report en cours...' : 'Tout reporter à demain'}</Text>
          </Pressable>
        </View>
      )}

      <Text style={styles.label}>Qu'est-ce qui bascule à demain ?</Text>
      <TextInput
        style={styles.textarea}
        multiline
        placeholder="Ce n'est pas un échec, juste un déplacement..."
        placeholderTextColor={colors.textMuted}
        value={basculeDemain}
        onChangeText={setBasculeDemain}
      />

      <Text style={styles.label}>Comment tu te sens, là, maintenant ?</Text>
      <TextInput
        style={styles.textarea}
        multiline
        placeholder="En quelques mots..."
        placeholderTextColor={colors.textMuted}
        value={ressenti}
        onChangeText={setRessenti}
      />

      <Pressable style={styles.saveButton} onPress={save} disabled={saving}>
        <Text style={styles.saveButtonText}>{saving ? 'Enregistrement...' : 'Clore la journée'}</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  subtitle: { ...typography.body, color: colors.textMuted, marginBottom: spacing.lg },
  label: { ...typography.heading, fontSize: 15, marginBottom: spacing.xs, marginTop: spacing.md },
  textarea: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: spacing.md,
    minHeight: 80,
    textAlignVertical: 'top',
    fontSize: 15,
    color: colors.text,
  },
  saveButton: { backgroundColor: colors.primary, borderRadius: 12, padding: spacing.md, alignItems: 'center', marginTop: spacing.xl },
  saveButtonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 16 },
  rolloverCard: { backgroundColor: colors.primaryMuted, borderRadius: 12, padding: spacing.md, marginTop: spacing.md },
  rolloverTitle: { ...typography.body, fontFamily: fonts.bold },
  rolloverSubtitle: { ...typography.caption, marginTop: 2, marginBottom: spacing.sm },
  rolloverTask: { ...typography.body, fontSize: 14, marginBottom: 2 },
  rolloverButton: { backgroundColor: colors.primary, borderRadius: 10, paddingVertical: spacing.sm, alignItems: 'center', marginTop: spacing.sm },
  rolloverButtonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 14 },
});
