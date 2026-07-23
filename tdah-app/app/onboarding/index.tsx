import { useState } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { router } from 'expo-router';
import { supabase } from '../../lib/supabase/client';
import { useAuth } from '../../lib/supabase/AuthProvider';
import { colors, spacing, typography, fonts } from '../../constants/theme';

type Step = {
  question: string;
  helper?: string;
  field: 'chronotype' | 'profil_masking' | 'preference_ton' | 'preference_gamification';
  options: { label: string; value: string }[];
};

const steps: Step[] = [
  {
    question: 'Plutôt du matin ou du soir ?',
    field: 'chronotype',
    options: [
      { label: 'Du matin', value: 'matin' },
      { label: 'Du soir', value: 'soir' },
      { label: 'Ça dépend des jours', value: 'neutre' },
    ],
  },
  {
    question: 'Tu dirais que tu "masques" beaucoup en société ?',
    helper: 'Faire semblant que tout va bien, se forcer à paraître organisé — même si en interne c’est le chaos.',
    field: 'profil_masking',
    options: [
      { label: 'Pas vraiment', value: 'faible' },
      { label: 'Un peu, selon les contextes', value: 'moyen' },
      { label: 'Énormément, ça m’épuise', value: 'eleve' },
    ],
  },
  {
    question: 'Comment tu veux que l’app te parle ?',
    field: 'preference_ton',
    options: [
      { label: 'Direct, sans détour', value: 'direct' },
      { label: 'Doux et bienveillant', value: 'doux' },
      { label: 'Avec un peu d’humour', value: 'humoristique' },
    ],
  },
  {
    question: 'Les petites récompenses/animations, tu en veux combien ?',
    field: 'preference_gamification',
    options: [
      { label: 'Beaucoup, ça me motive', value: 'intense' },
      { label: 'Discret, sans en faire trop', value: 'discrete' },
      { label: 'Aucune, ça me distrait', value: 'off' },
    ],
  },
];

export default function OnboardingScreen() {
  const { session } = useAuth();
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const step = steps[stepIndex];
  const isLast = stepIndex === steps.length - 1;

  async function selectOption(value: string) {
    const nextAnswers = { ...answers, [step.field]: value };
    setAnswers(nextAnswers);

    if (isLast && session) {
      await supabase
        .from('profiles')
        .update({ ...nextAnswers, onboarding_complete: true })
        .eq('id', session.user.id);
      router.replace('/(tabs)');
    } else {
      setStepIndex((i) => i + 1);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.progressRow}>
        {steps.map((_, i) => (
          <View key={i} style={[styles.progressDot, i <= stepIndex && styles.progressDotActive]} />
        ))}
      </View>

      <Text style={styles.question}>{step.question}</Text>
      {step.helper && <Text style={styles.helper}>{step.helper}</Text>}

      <View style={styles.options}>
        {step.options.map((opt) => (
          <Pressable key={opt.value} style={styles.optionButton} onPress={() => selectOption(opt.value)}>
            <Text style={styles.optionText}>{opt.label}</Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.footnote}>Tu pourras changer ça à tout moment dans ton profil.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing.lg, justifyContent: 'center' },
  progressRow: { flexDirection: 'row', gap: spacing.xs, justifyContent: 'center', marginBottom: spacing.xl },
  progressDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.border },
  progressDotActive: { backgroundColor: colors.primary },
  question: { ...typography.title, fontSize: 24, textAlign: 'center', marginBottom: spacing.sm },
  helper: { ...typography.caption, textAlign: 'center', marginBottom: spacing.lg, paddingHorizontal: spacing.md },
  options: { gap: spacing.sm, marginTop: spacing.lg },
  optionButton: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: spacing.md,
    alignItems: 'center',
  },
  optionText: { ...typography.body, fontFamily: fonts.medium },
  footnote: { ...typography.caption, textAlign: 'center', marginTop: spacing.xl },
});
