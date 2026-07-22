import { useMemo, type ReactNode } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { spacing, fonts, radius, type ThemeColors } from '../constants/theme';
import { useTheme } from '../lib/theme/ThemeProvider';
import { useSubscription } from '../lib/billing/stripe';

// Prêt à l'emploi mais non branché sur une fonctionnalité précise pour
// l'instant : la répartition gratuit/payant sera décidée plus tard, une fois
// toutes les fonctionnalités terminées. `<PremiumGate>` enveloppe alors le
// contenu à réserver, sans rien changer d'autre dans l'écran qui l'utilise.
export function PremiumGate({ children, label }: { children: ReactNode; label?: string }) {
  const { isPremium, loading } = useSubscription();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();

  if (loading || isPremium) return <>{children}</>;

  return (
    <Pressable style={styles.locked} onPress={() => router.push('/paiement')}>
      <Ionicons name="lock-closed-outline" size={16} color={colors.primary} />
      <Text style={styles.lockedText}>{label ?? 'Fonctionnalité Premium'}</Text>
    </Pressable>
  );
}

function makeStyles(colors: ThemeColors) {
  return StyleSheet.create({
    locked: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.xs,
      backgroundColor: colors.primaryMuted,
      borderRadius: radius.md,
      padding: spacing.md,
    },
    lockedText: { color: colors.primary, fontFamily: fonts.semibold, fontSize: 14 },
  });
}
