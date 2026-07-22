import { useCallback, useEffect, useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, FlatList, Alert } from 'react-native';
import { Stack } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import { Ionicons } from '@expo/vector-icons';
import { supabase } from '../lib/supabase/client';
import { useAuth } from '../lib/supabase/AuthProvider';
import { colors, spacing, typography } from '../constants/theme';

// Outil de "temporisation" pour les messages écrits en pleine détresse liée
// à un rejet perçu (RSD). L'app ne touche à aucune vraie messagerie : c'est
// un brouillon que l'utilisateur ouvre lui-même avant d'aller coller le
// texte ailleurs (SMS, email...), une fois la charge émotionnelle redescendue.
// À ne présenter qu'en outil de coping générique, jamais en vocabulaire
// diagnostique — la recherche sur la RSD reste émergente (pas d'échelle
// validée à ce jour).

type Draft = { id: string; contenu: string; envoyer_apres: string; statut: string };
const DELAYS_MIN = [10, 20, 30];

export default function BrouillonDiffereScreen() {
  const { session } = useAuth();
  const [contenu, setContenu] = useState('');
  const [delay, setDelay] = useState(20);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [now, setNow] = useState(Date.now());

  const load = useCallback(async () => {
    if (!session) return;
    const { data } = await supabase
      .from('delayed_drafts')
      .select('id, contenu, envoyer_apres, statut')
      .eq('statut', 'en_attente')
      .order('envoyer_apres', { ascending: true });
    setDrafts(data ?? []);
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  async function hold() {
    if (!contenu.trim() || !session) return;
    const envoyerApres = new Date(Date.now() + delay * 60 * 1000).toISOString();
    await supabase.from('delayed_drafts').insert({ user_id: session.user.id, contenu: contenu.trim(), envoyer_apres: envoyerApres });
    setContenu('');
    load();
  }

  async function cancelDraft(id: string) {
    await supabase.from('delayed_drafts').update({ statut: 'annule' }).eq('id', id);
    load();
  }

  async function copyAndClear(draft: Draft) {
    await Clipboard.setStringAsync(draft.contenu);
    await supabase.from('delayed_drafts').update({ statut: 'valide' }).eq('id', draft.id);
    Alert.alert('Copié', 'Le texte est dans ton presse-papier — tu peux le coller où tu voulais l’envoyer.');
    load();
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ headerShown: true, title: 'Brouillon différé', headerBackTitle: 'Profil' }} />

      <Text style={styles.subtitle}>
        Tu écris ce que tu as sur le cœur, et ça reste ici quelques minutes avant que tu puisses le copier ailleurs. Rien
        n’est envoyé automatiquement.
      </Text>

      <TextInput
        style={styles.textarea}
        multiline
        placeholder="Écris ce que tu veux dire..."
        placeholderTextColor={colors.textMuted}
        value={contenu}
        onChangeText={setContenu}
      />

      <Text style={styles.label}>Le garder combien de temps ?</Text>
      <View style={styles.delayRow}>
        {DELAYS_MIN.map((d) => (
          <Pressable key={d} style={[styles.delayChip, delay === d && styles.delayChipActive]} onPress={() => setDelay(d)}>
            <Text style={[styles.delayText, delay === d && styles.delayTextActive]}>{d} min</Text>
          </Pressable>
        ))}
      </View>

      <Pressable style={styles.holdButton} onPress={hold}>
        <Text style={styles.holdButtonText}>Mettre en attente</Text>
      </Pressable>

      <FlatList
        style={{ marginTop: spacing.lg }}
        data={drafts}
        keyExtractor={(d) => d.id}
        renderItem={({ item }) => {
          const remainingMs = new Date(item.envoyer_apres).getTime() - now;
          const ready = remainingMs <= 0;
          const remainingMin = Math.max(0, Math.ceil(remainingMs / 60000));
          return (
            <View style={styles.draftCard}>
              <Text style={styles.draftContent} numberOfLines={3}>
                {item.contenu}
              </Text>
              {ready ? (
                <View style={styles.draftActions}>
                  <Pressable style={styles.draftButton} onPress={() => copyAndClear(item)}>
                    <Ionicons name="copy-outline" size={16} color={colors.primary} />
                    <Text style={styles.draftButtonText}>Copier</Text>
                  </Pressable>
                  <Pressable style={styles.draftButton} onPress={() => cancelDraft(item.id)}>
                    <Ionicons name="trash-outline" size={16} color={colors.warning} />
                    <Text style={[styles.draftButtonText, { color: colors.warning }]}>Supprimer</Text>
                  </Pressable>
                </View>
              ) : (
                <Text style={styles.caption}>Disponible dans {remainingMin} min</Text>
              )}
            </View>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing.lg },
  subtitle: { ...typography.body, color: colors.textMuted, marginBottom: spacing.md },
  textarea: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: spacing.md,
    minHeight: 120,
    textAlignVertical: 'top',
    fontSize: 15,
    color: colors.text,
  },
  label: { ...typography.caption, marginTop: spacing.md, marginBottom: spacing.xs },
  delayRow: { flexDirection: 'row', gap: spacing.sm },
  delayChip: { borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingVertical: spacing.xs, paddingHorizontal: spacing.md },
  delayChipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
  delayText: { color: colors.textMuted },
  delayTextActive: { color: colors.primary, fontWeight: '600' },
  holdButton: { backgroundColor: colors.primary, borderRadius: 12, padding: spacing.md, alignItems: 'center', marginTop: spacing.lg },
  holdButtonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  draftCard: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: spacing.md, marginBottom: spacing.sm },
  draftContent: { ...typography.body, marginBottom: spacing.xs },
  caption: { ...typography.caption },
  draftActions: { flexDirection: 'row', gap: spacing.lg, marginTop: spacing.xs },
  draftButton: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  draftButtonText: { color: colors.primary, fontSize: 13, fontWeight: '500' },
});
