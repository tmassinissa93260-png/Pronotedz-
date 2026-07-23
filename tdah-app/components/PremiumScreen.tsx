import { useMemo, type ReactNode } from 'react';
import { View, Text, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { spacing, fonts, radius, makeTypography, type ThemeColors } from '../constants/theme';
import { useTheme } from '../lib/theme/ThemeProvider';
import { useSubscription } from '../lib/billing/stripe';

// Filet de sécurité pour les écrans premium atteints directement (lien
// profond, favori) plutôt que via un bouton déjà verrouillé dans l'app —
// l'entrée normale (menu Outils, boutons du planning) bloque déjà avant
// d'arriver ici, ceci couvre le cas où quelqu'un contourne ce point d'entrée.
export function PremiumScreen({ label, children }: { label: string; children: ReactNode }) {
  const { isPremium, loading } = useSubscription();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  if (!isPremium) {
    return (
      <View style={styles.centered}>
        <Ionicons name="lock-closed-outline" size={40} color={colors.primary} />
        <Text style={styles.title}>{label}</Text>
        <Text style={styles.body}>Cette fonctionnalité fait partie de l'abonnement — l'app reste gratuite pour ton planning quotidien et tes check-ins.</Text>
        <Pressable style={styles.button} onPress={() => router.push('/paiement')}>
          <Text style={styles.buttonText}>Voir les offres</Text>
        </Pressable>
        <Pressable onPress={() => router.back()} style={{ marginTop: spacing.md }}>
          <Text style={styles.back}>Retour</Text>
        </Pressable>
      </View>
    );
  }

  return <>{children}</>;
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
    centered: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center', padding: spacing.lg, gap: spacing.sm },
    title: { ...typography.heading, marginTop: spacing.sm, textAlign: 'center' },
    body: { ...typography.body, color: colors.textMuted, textAlign: 'center' },
    button: { marginTop: spacing.md, backgroundColor: colors.primary, borderRadius: radius.md, paddingVertical: spacing.md, paddingHorizontal: spacing.xl },
    buttonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 15 },
    back: { color: colors.textMuted, fontSize: 14 },
  });
}
