import { useEffect, useRef, useState } from 'react';
import { View, Text, Pressable, StyleSheet, Animated, Easing, Modal } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import * as Speech from 'expo-speech';
import { supabase } from '../../lib/supabase/client';
import { useAuth } from '../../lib/supabase/AuthProvider';
import { useProfile } from '../../lib/supabase/useProfile';
import { bumpStreak } from '../../lib/supabase/streak';
import { maybeUnlockTenSessionsBadge } from '../../lib/supabase/badges';
import { useReward } from '../../lib/rewards/RewardProvider';
import { InteroceptionCheckIn } from '../../components/InteroceptionCheckIn';
import { colors, spacing, typography } from '../../constants/theme';

type Mode = 'responsabilisation' | 'coregulation';
const CHECKIN_THRESHOLD_MINUTES = 45;
const DURATIONS = [15, 25, 45] as const;
// En dessous de ce ratio du temps cible, on marque un temps de pause avant
// de confirmer l'arrêt — friction consciente contre l'abandon impulsif
// (façon One Sec), pas un blocage, juste un ralentissement d'une poignée
// de secondes pour laisser le choix redevenir conscient.
const EARLY_EXIT_RATIO = 0.2;

export default function FocusScreen() {
  const { session } = useAuth();
  const profile = useProfile();
  const { celebrate } = useReward();
  const { tache: tacheParam } = useLocalSearchParams<{ tache?: string }>();
  const [targetMinutes, setTargetMinutes] = useState<number | null>(25);
  const [activeSession, setActiveSession] = useState<{ id: string; mode: Mode; startedAt: number } | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [sessionTarget, setSessionTarget] = useState<number | null>(null);
  const [checkInVisible, setCheckInVisible] = useState(false);
  const [earlyExitPause, setEarlyExitPause] = useState(false);
  const [earlyExitReady, setEarlyExitReady] = useState(false);
  const breathAnim = useRef(new Animated.Value(1)).current;
  const focusedTaskTitle = tacheParam ? decodeURIComponent(tacheParam) : null;

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
    setSessionTarget(targetMinutes);
    setElapsedSeconds(0);

    // Narration vocale façon Routinery : annoncer plutôt qu'obliger à lire —
    // moins de charge visuelle au moment où on démarre.
    const modeLabel = mode === 'coregulation' ? 'co-régulation' : 'responsabilisation';
    const dureeLabel = targetMinutes ? `${targetMinutes} minutes` : 'en durée libre';
    const tacheLabel = focusedTaskTitle ? ` sur "${focusedTaskTitle}"` : '';
    Speech.speak(`C'est parti pour une session de ${modeLabel}${tacheLabel}, ${dureeLabel}.`, { language: 'fr-FR' });
  }

  function addFiveMinutes() {
    setSessionTarget((prev) => (prev ?? 0) + 5);
  }

  function requestEndSession() {
    const target = sessionTarget;
    const tropTot = target != null && elapsedSeconds < target * 60 * EARLY_EXIT_RATIO;
    if (tropTot) {
      setEarlyExitReady(false);
      setEarlyExitPause(true);
      setTimeout(() => setEarlyExitReady(true), 5000);
      return;
    }
    endSession();
  }

  async function endSession() {
    if (!activeSession || !session) return;
    const dureeMinutes = Math.max(1, Math.round(elapsedSeconds / 60));
    await supabase
      .from('sessions')
      .update({ ended_at: new Date().toISOString(), duree_minutes: dureeMinutes })
      .eq('id', activeSession.id);

    await bumpStreak(session.user.id);
    await maybeUnlockTenSessionsBadge(session.user.id);
    celebrate(profile?.preference_gamification ?? 'discrete');

    if (dureeMinutes >= CHECKIN_THRESHOLD_MINUTES) {
      setCheckInVisible(true);
    }
    setActiveSession(null);
    setEarlyExitPause(false);
  }

  const remainingSeconds = sessionTarget != null ? Math.max(0, sessionTarget * 60 - elapsedSeconds) : elapsedSeconds;
  const minutes = String(Math.floor(remainingSeconds / 60)).padStart(2, '0');
  const seconds = String(remainingSeconds % 60).padStart(2, '0');
  const isOvertime = sessionTarget != null && elapsedSeconds > sessionTarget * 60;

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
        {focusedTaskTitle && <Text style={styles.focusedTask}>🎯 {focusedTaskTitle}</Text>}
        {activeSession.mode === 'coregulation' ? (
          <Animated.View style={[styles.breathCircle, { transform: [{ scale: breathAnim }] }]} />
        ) : (
          <Text style={styles.checkinLabel}>On vérifie ensemble de temps en temps 👋</Text>
        )}
        <Text style={styles.timer}>
          {isOvertime ? '+' : ''}{minutes}:{seconds}
        </Text>
        <Text style={styles.sessionMode}>
          {activeSession.mode === 'coregulation' ? 'Mode co-régulation' : 'Mode responsabilisation'}
          {sessionTarget != null ? ` · objectif ${sessionTarget} min` : ''}
        </Text>
        <View style={styles.sessionActions}>
          {sessionTarget != null && (
            <Pressable style={styles.plusFiveButton} onPress={addFiveMinutes}>
              <Text style={styles.plusFiveText}>+5 min</Text>
            </Pressable>
          )}
          <Pressable style={styles.endButton} onPress={requestEndSession}>
            <Text style={styles.endButtonText}>Terminer la session</Text>
          </Pressable>
        </View>
        {checkInModal}

        <Modal visible={earlyExitPause} transparent animationType="fade">
          <View style={styles.pauseOverlay}>
            <View style={styles.pauseCard}>
              <Text style={styles.pauseTitle}>Une seconde…</Text>
              <Text style={styles.pauseBody}>
                Tu arrêtes très tôt par rapport à ton objectif. Prends juste un instant avant de confirmer — pas d'obligation de continuer.
              </Text>
              <View style={styles.pauseActions}>
                <Pressable style={styles.pauseCancelButton} onPress={() => setEarlyExitPause(false)}>
                  <Text style={styles.pauseCancelText}>Continuer à travailler</Text>
                </Pressable>
                <Pressable
                  style={[styles.pauseConfirmButton, !earlyExitReady && styles.pauseConfirmButtonDisabled]}
                  disabled={!earlyExitReady}
                  onPress={endSession}
                >
                  <Text style={styles.pauseConfirmText}>{earlyExitReady ? 'Arrêter quand même' : 'Patiente…'}</Text>
                </Pressable>
              </View>
            </View>
          </View>
        </Modal>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Focus</Text>
      <Text style={styles.subtitle}>Travailler à côté de quelqu’un — même une présence IA — aide à démarrer et à tenir.</Text>

      <Text style={styles.durationLabel}>Durée</Text>
      <View style={styles.durationRow}>
        {DURATIONS.map((d) => (
          <Pressable
            key={d}
            style={[styles.durationChip, targetMinutes === d && styles.durationChipActive]}
            onPress={() => setTargetMinutes(d)}
          >
            <Text style={[styles.durationText, targetMinutes === d && styles.durationTextActive]}>{d} min</Text>
          </Pressable>
        ))}
        <Pressable
          style={[styles.durationChip, targetMinutes === null && styles.durationChipActive]}
          onPress={() => setTargetMinutes(null)}
        >
          <Text style={[styles.durationText, targetMinutes === null && styles.durationTextActive]}>Libre</Text>
        </Pressable>
      </View>

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
  subtitle: { ...typography.body, color: colors.textMuted, marginBottom: spacing.lg },
  durationLabel: { ...typography.caption, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: spacing.xs },
  durationRow: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.lg },
  durationChip: { borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingVertical: 6, paddingHorizontal: spacing.md },
  durationChipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
  durationText: { fontSize: 13, color: colors.textMuted },
  durationTextActive: { color: colors.primary, fontWeight: '600' },
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
  sessionActions: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  plusFiveButton: { borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingVertical: spacing.md, paddingHorizontal: spacing.md },
  plusFiveText: { color: colors.text, fontWeight: '600', fontSize: 14 },
  endButton: { backgroundColor: colors.primary, borderRadius: 12, paddingVertical: spacing.md, paddingHorizontal: spacing.xl },
  endButtonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  focusedTask: { ...typography.heading, fontSize: 17, marginBottom: spacing.lg, textAlign: 'center' },
  pauseOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', alignItems: 'center', padding: spacing.lg },
  pauseCard: { backgroundColor: colors.surface, borderRadius: 16, padding: spacing.lg, width: '100%', maxWidth: 340 },
  pauseTitle: { ...typography.heading, marginBottom: spacing.xs },
  pauseBody: { ...typography.body, color: colors.textMuted, marginBottom: spacing.lg },
  pauseActions: { gap: spacing.sm },
  pauseCancelButton: { borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingVertical: spacing.md, alignItems: 'center' },
  pauseCancelText: { color: colors.text, fontWeight: '600', fontSize: 14 },
  pauseConfirmButton: { backgroundColor: colors.primary, borderRadius: 12, paddingVertical: spacing.md, alignItems: 'center' },
  pauseConfirmButtonDisabled: { opacity: 0.4 },
  pauseConfirmText: { color: '#fff', fontWeight: '600', fontSize: 14 },
});
