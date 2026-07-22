import { useEffect, useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, ScrollView, Alert } from 'react-native';
import { Stack, useRouter } from 'expo-router';
import { supabase } from '../lib/supabase/client';
import { useAuth } from '../lib/supabase/AuthProvider';
import { colors, spacing, typography } from '../constants/theme';

// Rituel de clôture façon Sunsama : 3 questions courtes pour fermer la
// journée consciemment plutôt que de la laisser juste s'arrêter en carafe
// avec une liste de tâches non finies qui culpabilise le lendemain.

const today = () => new Date().toISOString().slice(0, 10);

export default function RituelFinJourneeScreen() {
  const { session } = useAuth();
  const router = useRouter();
  const [accompli, setAccompli] = useState('');
  const [basculeDemain, setBasculeDemain] = useState('');
  const [ressenti, setRessenti] = useState('');
  const [saving, setSaving] = useState(false);
  const [dejaFait, setDejaFait] = useState(false);

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
  }, [session]);

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
  saveButtonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});
