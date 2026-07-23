import { useEffect, useState, useCallback } from 'react';
import { Alert } from 'react-native';
import { useRouter } from 'expo-router';
import * as Linking from 'expo-linking';
import { supabase } from '../supabase/client';
import { useAuth } from '../supabase/AuthProvider';

export type SubscriptionStatus = 'gratuit' | 'actif' | 'annule' | 'expire';
export type Plan = 'mensuel' | 'annuel';

export async function startCheckout(userId: string, plan: Plan): Promise<string> {
  // Linking.createURL calcule le bon schéma pour l'environnement courant
  // (exp://... sous Expo Go, tdahapp://... dans un build EAS) — le coder en
  // dur aurait cassé le retour dans l'app pendant les tests sous Expo Go.
  const redirectBase = Linking.createURL('checkout-retour');
  const { data, error } = await supabase.rpc('create_checkout_session', {
    p_user_id: userId,
    p_plan: plan,
    p_redirect_base: redirectBase,
  });
  if (error) throw error;
  return (data as { url: string }).url;
}

export async function confirmCheckout(userId: string, sessionId: string): Promise<SubscriptionStatus> {
  const { data, error } = await supabase.rpc('confirm_checkout_session', { p_user_id: userId, p_session_id: sessionId });
  if (error) throw error;
  return (data as { statut: SubscriptionStatus }).statut;
}

export async function refreshSubscription(userId: string): Promise<SubscriptionStatus> {
  const { data, error } = await supabase.rpc('refresh_subscription_status', { p_user_id: userId });
  if (error) throw error;
  return (data as { statut: SubscriptionStatus }).statut;
}

export async function getSubscription(userId: string): Promise<{ statut: SubscriptionStatus; plan: Plan | null; periode_fin: string | null } | null> {
  const { data, error } = await supabase
    .from('subscriptions')
    .select('statut, plan, periode_fin')
    .eq('user_id', userId)
    .maybeSingle();
  if (error) throw error;
  return data;
}

async function getEssaiPremiumFin(userId: string): Promise<string | null> {
  const { data, error } = await supabase
    .from('profiles')
    .select('essai_premium_fin')
    .eq('id', userId)
    .maybeSingle();
  if (error) throw error;
  return data?.essai_premium_fin ?? null;
}

const MS_PAR_JOUR = 24 * 60 * 60 * 1000;

// Lecture seule et légère (pas d'appel Stripe) — utilisable partout, y
// compris par usePremiumGate() et <PremiumScreen>. Le rafraîchissement réel
// côté Stripe (refreshSubscription) reste réservé à l'écran Profil pour
// éviter de multiplier les appels API à chaque montage de composant.
export function useSubscription() {
  const { session } = useAuth();
  const [statut, setStatut] = useState<SubscriptionStatus>('gratuit');
  const [essaiFin, setEssaiFin] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    if (!session) return;
    Promise.all([getSubscription(session.user.id), getEssaiPremiumFin(session.user.id)])
      .then(([sub, essai]) => {
        setStatut(sub?.statut ?? 'gratuit');
        setEssaiFin(essai);
      })
      .finally(() => setLoading(false));
  }, [session]);

  useEffect(() => {
    reload();
  }, [reload]);

  const essaiActif = essaiFin != null && new Date(essaiFin).getTime() > Date.now();
  const essaiJoursRestants = essaiActif ? Math.max(1, Math.ceil((new Date(essaiFin!).getTime() - Date.now()) / MS_PAR_JOUR)) : 0;
  const abonnementActif = statut === 'actif';

  return {
    statut,
    isPremium: abonnementActif || essaiActif,
    // Essai en cours, distinct d'un vrai abonnement — sert à afficher la
    // bannière de relance avant la fin de l'essai plutôt que le badge "actif".
    isEssaiActif: essaiActif && !abonnementActif,
    essaiJoursRestants,
    loading,
    reload,
  };
}

// Point d'entrée unique pour verrouiller une action derrière l'abonnement —
// un seul endroit pour le ton du message (jamais culpabilisant, cohérent
// avec le reste de l'app) plutôt que du texte de paywall dupliqué partout.
export function usePremiumGate() {
  const { isPremium, statut, isEssaiActif, essaiJoursRestants } = useSubscription();
  const router = useRouter();

  function gate(label: string, action: () => void) {
    if (isPremium) {
      action();
      return;
    }
    Alert.alert(
      'Fonctionnalité Premium',
      `${label} fait partie de l'abonnement — l'app reste gratuite pour ton planning quotidien et tes check-ins.`,
      [
        { text: 'Plus tard', style: 'cancel' },
        { text: 'Voir les offres', onPress: () => router.push('/paiement') },
      ]
    );
  }

  return { isPremium, gate, statut, isEssaiActif, essaiJoursRestants };
}
