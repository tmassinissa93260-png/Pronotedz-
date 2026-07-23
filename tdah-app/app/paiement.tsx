import { useMemo, useState } from 'react';
import { View, Text, Pressable, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { Stack } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../lib/supabase/AuthProvider';
import { spacing, fonts, radius, shadow, makeTypography, type ThemeColors } from '../constants/theme';
import { useTheme } from '../lib/theme/ThemeProvider';
import { startCheckout, useSubscription, type Plan } from '../lib/billing/stripe';

// Stripe Checkout (page hébergée, ouverte dans le navigateur du téléphone)
// plutôt que le SDK natif @stripe/stripe-react-native, qui casserait Expo Go
// — voir supabase/migrations/0015_stripe_subscriptions.sql pour le détail.
// Aucune fonctionnalité n'est verrouillée pour l'instant : cet écran existe
// pour que l'abonnement soit possible, la répartition gratuit/payant sera
// décidée plus tard.

export default function PaiementScreen() {
  const { session } = useAuth();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { statut, isEssaiActif, essaiJoursRestants, loading } = useSubscription();
  const [starting, setStarting] = useState<Plan | null>(null);

  // La confirmation réelle (vérification auprès de Stripe + activation) se
  // fait dans app/checkout-retour.tsx, qui reçoit le lien de retour — pas
  // ici, pour n'avoir qu'un seul endroit qui écrit le statut d'abonnement.
  async function choisirPlan(plan: Plan) {
    if (!session) return;
    setStarting(plan);
    try {
      const url = await startCheckout(session.user.id, plan);
      await WebBrowser.openAuthSessionAsync(url, Linking.createURL('checkout-retour'));
    } catch {
      Alert.alert('Erreur', 'Impossible d’ouvrir la page de paiement pour le moment. Réessaie dans un instant.');
    } finally {
      setStarting(null);
    }
  }

  return (
    <View style={styles.container}>
      <Stack.Screen
        options={{
          headerShown: true,
          title: 'Abonnement',
          headerBackTitle: 'Retour',
          headerStyle: { backgroundColor: colors.surface },
          headerTintColor: colors.text,
        }}
      />

      {loading ? (
        <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.xl }} />
      ) : statut === 'actif' ? (
        <View style={styles.activeBox}>
          <Ionicons name="checkmark-circle" size={28} color={colors.success} />
          <Text style={styles.activeText}>Ton abonnement est actif — merci de soutenir l’app 💜</Text>
        </View>
      ) : (
        <>
          <Text style={styles.subtitle}>
            {isEssaiActif
              ? `Ton essai gratuit se termine dans ${essaiJoursRestants} jour${essaiJoursRestants > 1 ? 's' : ''} — passe à l’abonnement maintenant pour ne rien perdre ensuite.`
              : statut === 'annule' || statut === 'expire'
              ? 'Ton abonnement précédent est terminé — tu peux le reprendre à tout moment.'
              : 'Ton essai gratuit est terminé, mais l’app reste utilisable pour ton planning quotidien.'}
          </Text>

          <Pressable style={styles.planCard} onPress={() => choisirPlan('mensuel')} disabled={starting !== null}>
            <Text style={styles.planTitle}>Mensuel</Text>
            <Text style={styles.planDesc}>Résiliable à tout moment, sans engagement.</Text>
            {starting === 'mensuel' && <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.sm }} />}
          </Pressable>

          <Pressable style={[styles.planCard, styles.planCardHighlight]} onPress={() => choisirPlan('annuel')} disabled={starting !== null}>
            <Text style={styles.planTitle}>Annuel</Text>
            <Text style={styles.planDesc}>Le plus avantageux sur l’année.</Text>
            {starting === 'annuel' && <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.sm }} />}
          </Pressable>
        </>
      )}
    </View>
  );
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background, padding: spacing.lg },
    subtitle: { ...typography.body, color: colors.textMuted, marginBottom: spacing.lg },
    planCard: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: spacing.lg,
      marginBottom: spacing.md,
      ...shadow.soft,
    },
    planCardHighlight: { borderWidth: 1.5, borderColor: colors.primary },
    planTitle: { ...typography.heading, marginBottom: spacing.xs },
    planDesc: { ...typography.body, color: colors.textMuted },
    activeBox: {
      backgroundColor: colors.successMuted,
      borderRadius: radius.lg,
      padding: spacing.lg,
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      marginTop: spacing.md,
    },
    activeText: { ...typography.body, flex: 1 },
  });
}
