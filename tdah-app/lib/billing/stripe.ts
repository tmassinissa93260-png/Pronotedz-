import { useEffect, useState, useCallback } from 'react';
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

// Lecture seule et légère (pas d'appel Stripe) — utilisable partout, y
// compris dans un futur <PremiumGate>. Le rafraîchissement réel côté
// Stripe (refreshSubscription) reste réservé à l'écran Profil pour éviter
// de multiplier les appels API à chaque montage de composant.
export function useSubscription() {
  const { session } = useAuth();
  const [statut, setStatut] = useState<SubscriptionStatus>('gratuit');
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    if (!session) return;
    getSubscription(session.user.id)
      .then((sub) => setStatut(sub?.statut ?? 'gratuit'))
      .finally(() => setLoading(false));
  }, [session]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { statut, isPremium: statut === 'actif', loading, reload };
}
