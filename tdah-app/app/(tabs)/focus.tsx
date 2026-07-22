import { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, Pressable, StyleSheet, Animated, Easing, Modal, TextInput, Share, ActivityIndicator } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Speech from 'expo-speech';
import type { RealtimeChannel } from '@supabase/supabase-js';
import { supabase } from '../../lib/supabase/client';
import { useAuth } from '../../lib/supabase/AuthProvider';
import { useProfile } from '../../lib/supabase/useProfile';
import { bumpStreak } from '../../lib/supabase/streak';
import { maybeUnlockTenSessionsBadge } from '../../lib/supabase/badges';
import { useReward } from '../../lib/rewards/RewardProvider';
import { InteroceptionCheckIn } from '../../components/InteroceptionCheckIn';
import { generateRoomCode, joinDuoRoom, sendDuoEvent, leaveDuoRoom, joinLobby, leaveLobby, type DuoEvent } from '../../lib/realtime/duoFocus';
import { CircularTimer } from '../../components/CircularTimer';
import { spacing, fonts, radius, shadow, makeTypography, type ThemeColors } from '../../constants/theme';
import { useTheme } from '../../lib/theme/ThemeProvider';

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
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { tache: tacheParam, tacheId } = useLocalSearchParams<{ tache?: string; tacheId?: string }>();
  const [targetMinutes, setTargetMinutes] = useState<number | null>(25);
  const [activeSession, setActiveSession] = useState<{ id: string; mode: Mode; startedAt: number } | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [sessionTarget, setSessionTarget] = useState<number | null>(null);
  const [checkInVisible, setCheckInVisible] = useState(false);
  const [earlyExitPause, setEarlyExitPause] = useState(false);
  const [earlyExitReady, setEarlyExitReady] = useState(false);
  const [paused, setPaused] = useState(false);
  const [focusSubtasks, setFocusSubtasks] = useState<{ id: string; titre: string; fait: boolean }[]>([]);
  const breathAnim = useRef(new Animated.Value(1)).current;
  const focusedTaskTitle = tacheParam ? decodeURIComponent(tacheParam) : null;

  // Sous-tâches visibles et cochables pendant la session (façon Tiimo) —
  // jusqu'ici elles n'existaient que dans la liste du planning, invisibles
  // une fois qu'on avait lancé le focus dessus.
  useEffect(() => {
    if (!tacheId) return;
    supabase
      .from('subtasks')
      .select('id, titre, fait, ordre')
      .eq('task_id', tacheId)
      .order('ordre', { ascending: true })
      .then(({ data }) => setFocusSubtasks(data ?? []));
  }, [tacheId]);

  async function toggleFocusSubtask(subtaskId: string, fait: boolean) {
    setFocusSubtasks((prev) => prev.map((s) => (s.id === subtaskId ? { ...s, fait: !fait } : s)));
    await supabase.from('subtasks').update({ fait: !fait }).eq('id', subtaskId);
  }

  // Focus à deux (façon Focusmate) : pas de vidéo (pas de SDK natif dispo
  // ici), mais la vraie présence mutuelle engagée — deux personnes réelles,
  // un minuteur partagé — via Supabase Realtime, sans build ni infra en plus.
  const [duoModalVisible, setDuoModalVisible] = useState(false);
  const [duoStep, setDuoStep] = useState<'choix' | 'rejoindre' | 'salle' | 'lobby'>('choix');
  const [duoCode, setDuoCode] = useState('');
  const [duoCodeInput, setDuoCodeInput] = useState('');
  const [duoPeerIds, setDuoPeerIds] = useState<string[]>([]);
  const [duoTargetMinutes, setDuoTargetMinutes] = useState<number | null>(25);
  const [duoPhase, setDuoPhase] = useState<'attente' | 'actif'>('attente');
  const [duoStartedAt, setDuoStartedAt] = useState<number | null>(null);
  const [duoElapsedSeconds, setDuoElapsedSeconds] = useState(0);
  const [duoToast, setDuoToast] = useState<string | null>(null);
  const [lobbyWaitingCount, setLobbyWaitingCount] = useState(0);
  const duoChannelRef = useRef<RealtimeChannel | null>(null);
  const lobbyChannelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    return () => {
      if (duoChannelRef.current) leaveDuoRoom(duoChannelRef.current);
      if (lobbyChannelRef.current) leaveLobby(lobbyChannelRef.current);
    };
  }, []);

  useEffect(() => {
    if (duoPhase !== 'actif' || !duoStartedAt) return;
    const interval = setInterval(() => setDuoElapsedSeconds(Math.floor((Date.now() - duoStartedAt) / 1000)), 1000);
    return () => clearInterval(interval);
  }, [duoPhase, duoStartedAt]);

  function handleDuoEvent(event: DuoEvent) {
    if (event.type === 'start') {
      setDuoTargetMinutes(event.targetMinutes);
      setDuoStartedAt(event.startedAt);
      setDuoElapsedSeconds(0);
      setDuoPhase('actif');
    } else if (event.type === 'encourage') {
      setDuoToast(event.emoji);
      setTimeout(() => setDuoToast(null), 2500);
    } else if (event.type === 'end') {
      setDuoToast('Ton binôme a terminé de son côté 👋');
      setTimeout(() => setDuoToast(null), 3500);
    }
  }

  function enterDuoRoom(code: string) {
    if (!session) return;
    const channel = joinDuoRoom(code, session.user.id, {
      onPeerIds: setDuoPeerIds,
      onEvent: handleDuoEvent,
    });
    duoChannelRef.current = channel;
    setDuoCode(code);
    setDuoStep('salle');
  }

  function createDuoRoom() {
    enterDuoRoom(generateRoomCode());
  }

  // Matching automatique : salle d'attente commune, appairage dès qu'un
  // deuxième inconnu s'y trouve aussi — pas besoin de connaître quelqu'un
  // ni de partager un code à l'avance.
  function joinMatchLobby() {
    if (!session) return;
    setDuoStep('lobby');
    const channel = joinLobby(session.user.id, {
      onWaitingCountChange: setLobbyWaitingCount,
      onMatched: (code) => {
        if (lobbyChannelRef.current) {
          leaveLobby(lobbyChannelRef.current);
          lobbyChannelRef.current = null;
        }
        enterDuoRoom(code);
      },
    });
    lobbyChannelRef.current = channel;
  }

  function cancelLobby() {
    if (lobbyChannelRef.current) {
      leaveLobby(lobbyChannelRef.current);
      lobbyChannelRef.current = null;
    }
    setLobbyWaitingCount(0);
    setDuoStep('choix');
  }

  function joinDuoRoomWithInput() {
    if (duoCodeInput.trim().length < 4) return;
    enterDuoRoom(duoCodeInput.trim());
  }

  async function shareDuoCode() {
    try {
      await Share.share({ message: `On fait une session de focus ensemble ? Rejoins-moi sur Compagnon TDAH avec le code : ${duoCode}` });
    } catch {
      // partage annulé ou indisponible, pas grave
    }
  }

  function startDuoSession() {
    if (!duoChannelRef.current) return;
    const startedAt = Date.now();
    sendDuoEvent(duoChannelRef.current, { type: 'start', targetMinutes: duoTargetMinutes, startedAt });
    setDuoStartedAt(startedAt);
    setDuoElapsedSeconds(0);
    setDuoPhase('actif');
  }

  function sendEncouragement(emoji: string) {
    if (!duoChannelRef.current || !session) return;
    sendDuoEvent(duoChannelRef.current, { type: 'encourage', emoji, from: session.user.id });
  }

  async function endDuoSession() {
    if (!session) return;
    const dureeMinutes = Math.max(1, Math.round(duoElapsedSeconds / 60));
    await supabase.from('sessions').insert({
      user_id: session.user.id,
      type: 'coregulation',
      partenaire: duoPeerIds[0] ?? 'inconnu',
      duree_minutes: dureeMinutes,
      started_at: new Date(duoStartedAt ?? Date.now()).toISOString(),
      ended_at: new Date().toISOString(),
    });
    if (duoChannelRef.current) {
      sendDuoEvent(duoChannelRef.current, { type: 'end' });
      leaveDuoRoom(duoChannelRef.current);
      duoChannelRef.current = null;
    }
    await bumpStreak(session.user.id);
    await maybeUnlockTenSessionsBadge(session.user.id);
    celebrate(profile?.preference_gamification ?? 'discrete');

    setDuoPhase('attente');
    setDuoStartedAt(null);
    setDuoModalVisible(false);
    setDuoStep('choix');
    setDuoCode('');
    setDuoCodeInput('');
    setDuoPeerIds([]);
  }

  function closeDuoSetup() {
    if (duoChannelRef.current) {
      leaveDuoRoom(duoChannelRef.current);
      duoChannelRef.current = null;
    }
    if (lobbyChannelRef.current) {
      leaveLobby(lobbyChannelRef.current);
      lobbyChannelRef.current = null;
    }
    setDuoModalVisible(false);
    setDuoStep('choix');
    setDuoCode('');
    setDuoCodeInput('');
    setDuoPeerIds([]);
    setLobbyWaitingCount(0);
  }

  const duoRemainingSeconds = duoTargetMinutes != null ? Math.max(0, duoTargetMinutes * 60 - duoElapsedSeconds) : duoElapsedSeconds;
  const duoMinutes = String(Math.floor(duoRemainingSeconds / 60)).padStart(2, '0');
  const duoSeconds = String(duoRemainingSeconds % 60).padStart(2, '0');

  useEffect(() => {
    if (!activeSession || paused) return;
    const interval = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, [activeSession, paused]);

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
    setPaused(false);

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

  function togglePause() {
    setPaused((p) => !p);
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
    setPaused(false);
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

  if (duoPhase === 'actif') {
    return (
      <View style={styles.sessionContainer}>
        <Text style={styles.checkinLabel}>👥 Session à deux · {duoPeerIds.length > 0 ? '1 binôme connecté' : 'en solo pour l\'instant'}</Text>
        <Text style={styles.timer}>{duoMinutes}:{duoSeconds}</Text>
        <Text style={styles.sessionMode}>{duoTargetMinutes != null ? `Objectif ${duoTargetMinutes} min` : 'Durée libre'}</Text>
        <View style={styles.encourageRow}>
          {['👏', '💪', '🙌', '🔥'].map((emoji) => (
            <Pressable key={emoji} style={styles.encourageButton} onPress={() => sendEncouragement(emoji)}>
              <Text style={styles.encourageEmoji}>{emoji}</Text>
            </Pressable>
          ))}
        </View>
        <Pressable style={styles.endButton} onPress={endDuoSession}>
          <Text style={styles.endButtonText}>Terminer la session</Text>
        </Pressable>
        {duoToast && (
          <View style={styles.duoToast}>
            <Text style={styles.duoToastText}>{duoToast}</Text>
          </View>
        )}
      </View>
    );
  }

  if (activeSession) {
    return (
      <View style={styles.sessionContainer}>
        {focusedTaskTitle && <Text style={styles.focusedTask}>🎯 {focusedTaskTitle}</Text>}
        {activeSession.mode === 'coregulation' && !paused && (
          <Animated.View style={[styles.breathCircle, { transform: [{ scale: breathAnim }] }]} />
        )}
        {activeSession.mode === 'responsabilisation' && (
          <Text style={styles.checkinLabel}>On vérifie ensemble de temps en temps 👋</Text>
        )}
        <CircularTimer progress={sessionTarget != null ? elapsedSeconds / (sessionTarget * 60) : 0}>
          <Text style={styles.timer}>
            {isOvertime ? '+' : ''}{minutes}:{seconds}
          </Text>
          {paused && <Text style={styles.pausedLabel}>En pause</Text>}
        </CircularTimer>
        <Text style={styles.sessionMode}>
          {activeSession.mode === 'coregulation' ? 'Mode co-régulation' : 'Mode responsabilisation'}
          {sessionTarget != null ? ` · objectif ${sessionTarget} min` : ''}
        </Text>
        {focusSubtasks.length > 0 && (
          <View style={styles.focusSubtasksBox}>
            {focusSubtasks.map((s) => (
              <Pressable key={s.id} style={styles.focusSubtaskRow} onPress={() => toggleFocusSubtask(s.id, s.fait)}>
                <Ionicons name={s.fait ? 'checkbox' : 'square-outline'} size={18} color={s.fait ? colors.success : colors.textMuted} />
                <Text style={[styles.focusSubtaskText, s.fait && styles.focusSubtaskTextDone]}>{s.titre}</Text>
              </Pressable>
            ))}
          </View>
        )}
        <View style={styles.sessionActions}>
          {sessionTarget != null && (
            <Pressable style={styles.plusFiveButton} onPress={addFiveMinutes}>
              <Text style={styles.plusFiveText}>+5 min</Text>
            </Pressable>
          )}
          <Pressable style={styles.pauseButton} onPress={togglePause}>
            <Ionicons name={paused ? 'play' : 'pause'} size={20} color={colors.text} />
          </Pressable>
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

      <Pressable style={[styles.modeCard, styles.duoCard]} onPress={() => setDuoModalVisible(true)}>
        <Text style={styles.modeTitle}>👥 Focus à deux</Text>
        <Text style={styles.modeDesc}>Une vraie personne, en même temps que toi, avec un minuteur partagé. Pas de vidéo — juste une présence réelle.</Text>
      </Pressable>

      {checkInModal}

      <Modal visible={duoModalVisible} transparent animationType="slide" onRequestClose={closeDuoSetup}>
        <View style={styles.duoModalBackdrop}>
          <View style={styles.duoModalCard}>
            {duoStep === 'choix' && (
              <>
                <Text style={styles.duoModalTitle}>Focus à deux</Text>
                <Text style={styles.duoModalSubtitle}>Crée une session et partage le code, ou rejoins quelqu'un qui t'a envoyé le sien.</Text>
                <Pressable style={styles.duoChoiceButton} onPress={joinMatchLobby}>
                  <Text style={styles.duoChoiceButtonText}>🔀 Trouver un binôme maintenant</Text>
                </Pressable>
                <Pressable style={[styles.duoChoiceButton, styles.duoChoiceButtonOutline]} onPress={createDuoRoom}>
                  <Text style={styles.duoChoiceButtonOutlineText}>Créer une session (avec un ami)</Text>
                </Pressable>
                <Pressable style={[styles.duoChoiceButton, styles.duoChoiceButtonOutline]} onPress={() => setDuoStep('rejoindre')}>
                  <Text style={styles.duoChoiceButtonOutlineText}>Rejoindre avec un code</Text>
                </Pressable>
                <Pressable onPress={closeDuoSetup} style={{ marginTop: spacing.md, alignSelf: 'center' }}>
                  <Text style={styles.duoModalCancel}>Annuler</Text>
                </Pressable>
              </>
            )}

            {duoStep === 'lobby' && (
              <>
                <Text style={styles.duoModalTitle}>Recherche d'un binôme…</Text>
                <View style={styles.lobbySpinnerRow}>
                  <ActivityIndicator color={colors.primary} size="large" />
                </View>
                <Text style={styles.duoModalSubtitle}>
                  {lobbyWaitingCount > 1
                    ? 'Quelqu\'un est là aussi — connexion en cours…'
                    : 'En attente que quelqu\'un d\'autre cherche un binôme en même temps que toi.'}
                </Text>
                <Pressable onPress={cancelLobby} style={{ marginTop: spacing.md, alignSelf: 'center' }}>
                  <Text style={styles.duoModalCancel}>Annuler la recherche</Text>
                </Pressable>
              </>
            )}

            {duoStep === 'rejoindre' && (
              <>
                <Text style={styles.duoModalTitle}>Rejoindre une session</Text>
                <Text style={styles.duoModalSubtitle}>Entre le code à 6 caractères qu'on t'a envoyé.</Text>
                <TextInput
                  style={styles.duoCodeInput}
                  placeholder="EX: A3F7K9"
                  placeholderTextColor={colors.textMuted}
                  autoCapitalize="characters"
                  value={duoCodeInput}
                  onChangeText={setDuoCodeInput}
                  maxLength={6}
                />
                <Pressable style={styles.duoChoiceButton} onPress={joinDuoRoomWithInput}>
                  <Text style={styles.duoChoiceButtonText}>Rejoindre</Text>
                </Pressable>
                <Pressable onPress={closeDuoSetup} style={{ marginTop: spacing.md, alignSelf: 'center' }}>
                  <Text style={styles.duoModalCancel}>Annuler</Text>
                </Pressable>
              </>
            )}

            {duoStep === 'salle' && (
              <>
                <Text style={styles.duoModalTitle}>Salle d'attente</Text>
                <Text style={styles.duoCodeDisplay}>{duoCode}</Text>
                <Pressable onPress={shareDuoCode} style={{ alignSelf: 'center', marginBottom: spacing.md }}>
                  <Text style={styles.duoShareText}>Partager le code →</Text>
                </Pressable>
                <Text style={styles.duoModalSubtitle}>
                  {duoPeerIds.length > 0 ? '✅ Ton binôme est connecté !' : 'En attente que quelqu\'un rejoigne...'}
                </Text>

                <Text style={styles.durationLabel}>Durée</Text>
                <View style={styles.durationRow}>
                  {DURATIONS.map((d) => (
                    <Pressable
                      key={d}
                      style={[styles.durationChip, duoTargetMinutes === d && styles.durationChipActive]}
                      onPress={() => setDuoTargetMinutes(d)}
                    >
                      <Text style={[styles.durationText, duoTargetMinutes === d && styles.durationTextActive]}>{d} min</Text>
                    </Pressable>
                  ))}
                </View>

                <Pressable style={styles.duoChoiceButton} onPress={startDuoSession} disabled={duoPeerIds.length === 0}>
                  <Text style={styles.duoChoiceButtonText}>Démarrer</Text>
                </Pressable>
                <Pressable onPress={closeDuoSetup} style={{ marginTop: spacing.md, alignSelf: 'center' }}>
                  <Text style={styles.duoModalCancel}>Quitter la salle</Text>
                </Pressable>
              </>
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing.lg },
  title: { ...typography.title, marginBottom: spacing.xs },
  subtitle: { ...typography.body, color: colors.textMuted, marginBottom: spacing.lg },
  durationLabel: { ...typography.caption, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: spacing.xs },
  durationRow: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.lg },
  durationChip: { borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingVertical: 6, paddingHorizontal: spacing.md },
  durationChipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
  durationText: { fontSize: 13, color: colors.textMuted },
  durationTextActive: { color: colors.primary, fontFamily: fonts.semibold },
  modeCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    ...shadow.soft,
  },
  modeTitle: { ...typography.heading, marginBottom: spacing.xs },
  modeDesc: { ...typography.body, color: colors.textMuted },
  sessionContainer: { flex: 1, backgroundColor: colors.background, justifyContent: 'center', alignItems: 'center', padding: spacing.lg },
  breathCircle: { width: 140, height: 140, borderRadius: 70, backgroundColor: colors.primaryMuted, marginBottom: spacing.xl },
  checkinLabel: { ...typography.body, marginBottom: spacing.xl },
  timer: { fontSize: 48, fontFamily: fonts.bold, color: colors.text, fontVariant: ['tabular-nums'] },
  sessionMode: { ...typography.caption, marginTop: spacing.xs, marginBottom: spacing.xl },
  sessionActions: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  focusSubtasksBox: { width: '100%', maxWidth: 320, marginBottom: spacing.lg, gap: spacing.xs },
  focusSubtaskRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  focusSubtaskText: { ...typography.body, fontSize: 15 },
  focusSubtaskTextDone: { textDecorationLine: 'line-through', color: colors.textMuted },
  plusFiveButton: { borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingVertical: spacing.md, paddingHorizontal: spacing.md },
  plusFiveText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 14 },
  endButton: { backgroundColor: colors.primary, borderRadius: radius.md, paddingVertical: spacing.md, paddingHorizontal: spacing.xl, ...shadow.soft },
  endButtonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 16 },
  pauseButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pausedLabel: { ...typography.caption, color: colors.warning, marginTop: spacing.xs, fontFamily: fonts.semibold },
  focusedTask: { ...typography.heading, fontSize: 17, marginBottom: spacing.lg, textAlign: 'center' },
  pauseOverlay: { flex: 1, backgroundColor: 'rgba(28,27,41,0.5)', justifyContent: 'center', alignItems: 'center', padding: spacing.lg },
  pauseCard: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.lg, width: '100%', maxWidth: 340, ...shadow.card },
  pauseTitle: { ...typography.heading, marginBottom: spacing.xs },
  pauseBody: { ...typography.body, color: colors.textMuted, marginBottom: spacing.lg },
  pauseActions: { gap: spacing.sm },
  pauseCancelButton: { borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingVertical: spacing.md, alignItems: 'center' },
  pauseCancelText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 14 },
  pauseConfirmButton: { backgroundColor: colors.primary, borderRadius: 12, paddingVertical: spacing.md, alignItems: 'center' },
  pauseConfirmButtonDisabled: { opacity: 0.4 },
  pauseConfirmText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 14 },
  duoCard: { borderWidth: 1.5, borderColor: colors.primary, borderStyle: 'dashed' },
  encourageRow: { flexDirection: 'row', gap: spacing.md, marginBottom: spacing.xl },
  encourageButton: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  encourageEmoji: { fontSize: 24 },
  duoToast: {
    position: 'absolute',
    top: spacing.xl,
    alignSelf: 'center',
    backgroundColor: colors.text,
    borderRadius: 20,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  duoToastText: { color: '#fff', fontSize: 16, fontFamily: fonts.semibold },
  duoModalBackdrop: { flex: 1, backgroundColor: 'rgba(28,27,41,0.45)', justifyContent: 'flex-end' },
  duoModalCard: { backgroundColor: colors.surface, borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: spacing.lg, paddingBottom: spacing.xl, ...shadow.card },
  duoModalTitle: { ...typography.heading, marginBottom: spacing.xs },
  duoModalSubtitle: { ...typography.caption, marginBottom: spacing.md },
  duoModalCancel: { color: colors.textMuted, fontSize: 14, textAlign: 'center', fontFamily: fonts.medium },
  duoChoiceButton: { backgroundColor: colors.primary, borderRadius: radius.md, padding: spacing.md, alignItems: 'center', marginTop: spacing.sm, ...shadow.soft },
  duoChoiceButtonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 16 },
  duoChoiceButtonOutline: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.border, shadowOpacity: 0, elevation: 0 },
  duoChoiceButtonOutlineText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 16 },
  duoCodeInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    fontSize: 20,
    fontFamily: fonts.semibold,
    letterSpacing: 4,
    textAlign: 'center',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  duoCodeDisplay: {
    fontSize: 36,
    fontFamily: fonts.bold,
    letterSpacing: 6,
    textAlign: 'center',
    color: colors.primary,
    marginVertical: spacing.md,
  },
  duoShareText: { color: colors.primary, fontFamily: fonts.semibold, fontSize: 14 },
  lobbySpinnerRow: { alignItems: 'center', marginVertical: spacing.lg },
  });
}
