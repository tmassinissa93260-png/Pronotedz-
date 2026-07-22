import { useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, Pressable } from 'react-native';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../lib/supabase/AuthProvider';
import { spacing, fonts, radius, makeTypography, type ThemeColors } from '../constants/theme';
import { useTheme } from '../lib/theme/ThemeProvider';
import { confirmCheckout } from '../lib/billing/stripe';

// Seul endroit qui écrit réellement le statut d'abonnement après un
// paiement — atteint via le lien tdahapp://checkout-retour renvoyé par
// Stripe Checkout (succès ou annulation).
export default function CheckoutRetourScreen() {
  const { session } = useAuth();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();
  const { session_id, annule } = useLocalSearchParams<{ session_id?: string; annule?: string }>();
  const [state, setState] = useState<'chargement' | 'succes' | 'annule' | 'erreur'>('chargement');

  useEffect(() => {
    if (annule) {
      setState('annule');
      return;
    }
    if (!session_id || !session) {
      setState('erreur');
      return;
    }
    confirmCheckout(session.user.id, session_id)
      .then((statut) => setState(statut === 'actif' ? 'succes' : 'erreur'))
      .catch(() => setState('erreur'));
  }, [session_id, annule, session]);

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ headerShown: false }} />
      {state === 'chargement' && (
        <>
          <ActivityIndicator color={colors.primary} size="large" />
          <Text style={styles.text}>Vérification du paiement...</Text>
        </>
      )}
      {state === 'succes' && (
        <>
          <Ionicons name="checkmark-circle" size={48} color={colors.success} />
          <Text style={styles.title}>Merci !</Text>
          <Text style={styles.text}>Ton abonnement est actif.</Text>
        </>
      )}
      {state === 'annule' && (
        <>
          <Ionicons name="close-circle-outline" size={48} color={colors.textMuted} />
          <Text style={styles.title}>Paiement annulé</Text>
          <Text style={styles.text}>Aucun souci, rien n’a été débité.</Text>
        </>
      )}
      {state === 'erreur' && (
        <>
          <Ionicons name="alert-circle-outline" size={48} color={colors.warning} />
          <Text style={styles.title}>Un problème est survenu</Text>
          <Text style={styles.text}>On n’a pas pu confirmer le paiement. Vérifie depuis Profil dans un instant.</Text>
        </>
      )}
      {state !== 'chargement' && (
        <Pressable style={styles.button} onPress={() => router.replace('/(tabs)')}>
          <Text style={styles.buttonText}>Retour à l’app</Text>
        </Pressable>
      )}
    </View>
  );
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center', padding: spacing.lg, gap: spacing.sm },
    title: { ...typography.heading, marginTop: spacing.sm },
    text: { ...typography.body, color: colors.textMuted, textAlign: 'center' },
    button: { marginTop: spacing.lg, backgroundColor: colors.primary, borderRadius: radius.md, paddingVertical: spacing.md, paddingHorizontal: spacing.xl },
    buttonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 15 },
  });
}
