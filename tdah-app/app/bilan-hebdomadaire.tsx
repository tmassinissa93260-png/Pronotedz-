import { useEffect, useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, ScrollView, Alert } from 'react-native';
import { Stack, useRouter } from 'expo-router';
import { supabase } from '../lib/supabase/client';
import { useAuth } from '../lib/supabase/AuthProvider';
import { colors, spacing, typography } from '../constants/theme';

// Équivalent hebdomadaire du rituel de fin de journée (0006) : trois
// questions réflexives, pas une nouvelle page de stats — le Dashboard fait
// déjà le "combien" (tâches, sessions...), ici c'est le "comment c'était".

function mondayOfThisWeek() {
  const d = new Date();
  const day = d.getDay() || 7;
  d.setDate(d.getDate() - day + 1);
  return d.toISOString().slice(0, 10);
}

export default function BilanHebdomadaireScreen() {
  const { session } = useAuth();
  const router = useRouter();
  const [pointsForts, setPointsForts] = useState('');
  const [aAmeliorer, setAAmeliorer] = useState('');
  const [prioriteSemaine, setPrioriteSemaine] = useState('');
  const [saving, setSaving] = useState(false);
  const [dejaFait, setDejaFait] = useState(false);
  const semaineDebut = mondayOfThisWeek();

  useEffect(() => {
    if (!session) return;
    supabase
      .from('weekly_reviews')
      .select('points_forts, a_ameliorer, priorite_semaine')
      .eq('semaine_debut', semaineDebut)
      .maybeSingle()
      .then(({ data }) => {
        if (data) {
          setPointsForts(data.points_forts ?? '');
          setAAmeliorer(data.a_ameliorer ?? '');
          setPrioriteSemaine(data.priorite_semaine ?? '');
          setDejaFait(true);
        }
      });
  }, [session]);

  async function save() {
    if (!session) return;
    setSaving(true);
    const { error } = await supabase.from('weekly_reviews').upsert(
      {
        user_id: session.user.id,
        semaine_debut: semaineDebut,
        points_forts: pointsForts.trim(),
        a_ameliorer: aAmeliorer.trim(),
        priorite_semaine: prioriteSemaine.trim(),
      },
      { onConflict: 'user_id,semaine_debut' }
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
      <Stack.Screen options={{ headerShown: true, title: 'Bilan de la semaine', headerBackTitle: 'Bilan' }} />

      <Text style={styles.subtitle}>
        {dejaFait ? 'Tu peux revenir sur tes réponses de cette semaine.' : 'Trois minutes pour prendre du recul, pas pour te noter.'}
      </Text>

      <Text style={styles.label}>Qu'est-ce qui a bien marché cette semaine ?</Text>
      <TextInput
        style={styles.textarea}
        multiline
        placeholder="Même une petite victoire compte..."
        placeholderTextColor={colors.textMuted}
        value={pointsForts}
        onChangeText={setPointsForts}
      />

      <Text style={styles.label}>Qu'est-ce qui a été difficile ?</Text>
      <TextInput
        style={styles.textarea}
        multiline
        placeholder="Sans jugement, juste un constat..."
        placeholderTextColor={colors.textMuted}
        value={aAmeliorer}
        onChangeText={setAAmeliorer}
      />

      <Text style={styles.label}>Quelle est ta priorité pour la semaine prochaine ?</Text>
      <TextInput
        style={styles.textarea}
        multiline
        placeholder="Une seule chose, pas dix..."
        placeholderTextColor={colors.textMuted}
        value={prioriteSemaine}
        onChangeText={setPrioriteSemaine}
      />

      <Pressable style={styles.saveButton} onPress={save} disabled={saving}>
        <Text style={styles.saveButtonText}>{saving ? 'Enregistrement...' : 'Enregistrer'}</Text>
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
  saveButtonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});
