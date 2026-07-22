import { useEffect, useRef, useState } from 'react';
import { View, Text, Pressable, StyleSheet, Animated, Easing } from 'react-native';
import { supabase } from '../../lib/supabase/client';
import { useAuth } from '../../lib/supabase/AuthProvider';
import { useProfile } from '../../lib/supabase/useProfile';
import { bumpStreak } from '../../lib/supabase/streak';
import { useReward } from '../../lib/rewards/RewardProvider';
import { InteroceptionCheckIn } from '../../components/InteroceptionCheckIn';
import { colors, spacing, typography } from '../../constants/theme';

type Mode = 'responsabilisation' | 'coregulation';
const CHECKIN_THRESHOLD_MINUTES = 45;

export default function FocusScreen() {
  const { session } = useAuth();
  const profile = useProfile();
  const { celebrate } = useReward();
  const [activeSession, setActiveSession] = useState<{ id: string; mode: Mode; startedAt: number } | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [checkInVisible, setCheckInVisible] = useState(false);
  const breathAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!activeSession) return;
    const interval = setInterval(() => setElapsedSeconds(Math.floor((Date.now() - activeSession.startedAt) / 1000)), 1000);
    return () => clearInterval(interval);
  }, [activeSession]);

  useEffect(() => {
    if (activeSession?.mode !== 'coregulation') return;
    // Respiration visuelle lente et continue : le rythme de l'IA "compagnon"
    // sert de point d'ancrage calme, indépendant de la vitesse de l'utilisateur.
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(breathAnim, { toValue: 1.35, duration: 4000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(breathAnim, { toValue: 1, duration: 4000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [activeSession?.mode]);

  async function startSession(mode: Mode) {
    if (!session) return;
    const { data, error } = await supabase
      .from('sessions')
      .insert({ user_id: session.user.id, type: mode, partenaire: 'ia' })
      .select('id')
      .single();
    if (error || !data) return;
    setActiveSession({ id: data.id, mode, startedAt: Date.now() });
    setElapsedSeconds(0);
  }

  async function endSession() {
    if (!activeSession || !session) return;
    const dureeMinutes = Math.max(1, Math.round(elapsedSeconds / 60));
    await supabase
      .from('sessions')
      .update({ ended_at: new Date().toISOString(), duree_minutes: dureeMinutes })
      .eq('id', activeSession.id);

    await bumpStreak(session.user.id);
    celebrate(profile?.preference_gamification ?? 'discrete');

    if (dureeMinutes >= CHECKIN_THRESHOLD_MINUTES) {
      setCheckInVisible(true);
    }
    setActiveSession(null);
  }

  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
  const seconds = String(elapsedSeconds % 60).padStart(2, '0');

  const checkInModal = (
    <InteroceptionCheckIn
      visible={checkInVisible}
      contexteDeclencheur="fin_session_focus_longue"
      gamificationPref={profile?.preference_gamification ?? 'discrete'}
      onClose={() => setCheckInVisible(false)}
    />
  );

  if (activeSession) {
    return (
      <View style={styles.sessionContainer}>
        {activeSession.mode === 'coregulation' ? (
          <Animated.View style={[styles.breathCircle, { transform: [{ scale: breathAnim }] }]} />
        ) : (
          <Text style={styles.checkinLabel}>On vérifie ensemble de temps en temps 👋</Text>
        )}
        <Text style={styles.timer}>{minutes}:{seconds}</Text>
        <Text style={styles.sessionMode}>
          {activeSession.mode === 'coregulation' ? 'Mode co-régulation' : 'Mode responsabilisation'}
        </Text>
        <Pressable style={styles.endButton} onPress={endSession}>
          <Text style={styles.endButtonText}>Terminer la session</Text>
        </Pressable>
        {checkInModal}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Focus</Text>
      <Text style={styles.subtitle}>Travailler à côté de quelqu’un — même une présence IA — aide à démarrer et à tenir.</Text>

      <Pressable style={styles.modeCard} onPress={() => startSession('coregulation')}>
        <Text style={styles.modeTitle}>Co-régulation</Text>
        <Text style={styles.modeDesc}>Une présence continue et calme en fond, qui t’aide à garder un rythme stable.</Text>
      </Pressable>

      <Pressable style={styles.modeCard} onPress={() => startSession('responsabilisation')}>
        <Text style={styles.modeTitle}>Responsabilisation</Text>
        <Text style={styles.modeDesc}>Des points de contact ponctuels pour vérifier que tu avances.</Text>
      </Pressable>

      {checkInModal}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing.lg },
  title: { ...typography.title, marginBottom: spacing.xs },
  subtitle: { ...typography.body, color: colors.textMuted, marginBottom: spacing.xl },
  modeCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  modeTitle: { ...typography.heading, marginBottom: spacing.xs },
  modeDesc: { ...typography.body, color: colors.textMuted },
  sessionContainer: { flex: 1, backgroundColor: colors.background, justifyContent: 'center', alignItems: 'center', padding: spacing.lg },
  breathCircle: { width: 140, height: 140, borderRadius: 70, backgroundColor: colors.primaryMuted, marginBottom: spacing.xl },
  checkinLabel: { ...typography.body, marginBottom: spacing.xl },
  timer: { fontSize: 48, fontWeight: '700', color: colors.text, fontVariant: ['tabular-nums'] },
  sessionMode: { ...typography.caption, marginTop: spacing.xs, marginBottom: spacing.xl },
  endButton: { backgroundColor: colors.primary, borderRadius: 12, paddingVertical: spacing.md, paddingHorizontal: spacing.xl },
  endButtonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});
