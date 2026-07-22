import { useMemo, useState } from 'react';
import { Modal, View, Text, Pressable, StyleSheet } from 'react-native';
import { supabase } from '../lib/supabase/client';
import { useAuth } from '../lib/supabase/AuthProvider';
import { bumpStreak } from '../lib/supabase/streak';
import { useReward } from '../lib/rewards/RewardProvider';
import { spacing, fonts, makeTypography, type ThemeColors } from '../constants/theme';
import { useTheme } from '../lib/theme/ThemeProvider';

// Question fermée plutôt qu'ouverte : les signaux internes (faim, fatigue...)
// n'atteignent pas toujours le seuil de conscience chez un cerveau TDAH.
// Une question à choix binaire coûte beaucoup moins cher cognitivement
// qu'un "comment tu te sens ?" en ce moment précis.

// "humeur" remplace la détection vocale émotionnelle prévue en V2 — analyser
// le ton de la voix demanderait un micro natif (bloqué dans Expo Go, comme
// la saisie vocale) et un modèle d'émotion externe non défini. Une question
// fermée sur l'humeur ressentie capture l'essentiel du signal utile
// (repérer une dérégulation dans la durée) sans dépendre de rien de natif.
const QUESTIONS: { type: 'faim' | 'fatigue' | 'toilettes' | 'humeur'; label: string; options: string[] }[] = [
  { type: 'faim', label: 'Ventre ?', options: ['Vide', 'Plein', 'Sais pas'] },
  { type: 'fatigue', label: 'Niveau d’énergie ?', options: ['À plat', 'Ça va', 'Sais pas'] },
  { type: 'toilettes', label: 'Besoin d’une pause ?', options: ['Oui', 'Non', 'Sais pas'] },
  { type: 'humeur', label: 'Ça va comment ?', options: ['😔 Dur', '😐 Neutre', '🙂 Bien'] },
];

type Props = {
  visible: boolean;
  contexteDeclencheur: string;
  gamificationPref: string;
  onClose: () => void;
};

export function InteroceptionCheckIn({ visible, contexteDeclencheur, gamificationPref, onClose }: Props) {
  const { session } = useAuth();
  const [question] = useState(() => QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)]);
  const { celebrate } = useReward();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  async function answer(reponse: string) {
    if (!session) return;
    await supabase.from('checkins').insert({
      user_id: session.user.id,
      type: question.type,
      reponse,
      contexte_declencheur: contexteDeclencheur,
    });
    const streak = await bumpStreak(session.user.id);
    celebrate(gamificationPref);
    onClose();
    if (streak?.reparation_utilisee) {
      // Le composant parent peut choisir de le signaler ; ici on reste discret.
    }
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>{question.label}</Text>
          <View style={styles.options}>
            {question.options.map((opt) => (
              <Pressable key={opt} style={styles.option} onPress={() => answer(opt)}>
                <Text style={styles.optionText}>{opt}</Text>
              </Pressable>
            ))}
          </View>
          <Pressable onPress={onClose}>
            <Text style={styles.dismiss}>Pas maintenant</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'flex-end' },
    card: {
      backgroundColor: colors.surface,
      borderTopLeftRadius: 24,
      borderTopRightRadius: 24,
      padding: spacing.lg,
      paddingBottom: spacing.xl,
    },
    title: { ...typography.heading, marginBottom: spacing.md, textAlign: 'center' },
    options: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
    option: {
      flex: 1,
      backgroundColor: colors.primaryMuted,
      borderRadius: 12,
      paddingVertical: spacing.md,
      alignItems: 'center',
    },
    optionText: { color: colors.primary, fontFamily: fonts.semibold },
    dismiss: { ...typography.caption, textAlign: 'center' },
  });
}
