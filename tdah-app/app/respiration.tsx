import { useEffect, useRef, useState } from 'react';
import { View, Text, Pressable, StyleSheet, Animated, Easing } from 'react-native';
import { Stack } from 'expo-router';
import { colors, spacing, typography, fonts } from '../constants/theme';

// Respiration guidée (façon RespiRelax) pour les moments de surcharge
// émotionnelle — accessible à tout moment, indépendamment d'une session
// focus. Aucune app TDAH concurrente analysée jusqu'ici n'a cet outil.
// Respiration carrée (box breathing) : 4s par phase, un rythme simple et
// reconnu pour redescendre en tension sans matériel ni musique.

const DURATIONS = [1, 3, 5] as const;
const PHASE_MS = 4000;
const PHASES: { label: string; scaleTo: number }[] = [
  { label: 'Inspire…', scaleTo: 1.4 },
  { label: 'Retiens…', scaleTo: 1.4 },
  { label: 'Expire…', scaleTo: 1 },
  { label: 'Retiens…', scaleTo: 1 },
];

export default function RespirationScreen() {
  const [targetMinutes, setTargetMinutes] = useState<number | null>(3);
  const [running, setRunning] = useState(false);
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const runningRef = useRef(false);

  useEffect(() => {
    if (!running) return;
    const interval = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, [running]);

  useEffect(() => {
    if (targetMinutes == null || !running) return;
    if (elapsedSeconds >= targetMinutes * 60) stop();
  }, [elapsedSeconds, targetMinutes, running]);

  function runPhase(i: number) {
    if (!runningRef.current) return;
    setPhaseIndex(i);
    Animated.timing(scaleAnim, {
      toValue: PHASES[i].scaleTo,
      duration: PHASE_MS,
      easing: Easing.inOut(Easing.ease),
      useNativeDriver: true,
    }).start(() => runPhase((i + 1) % PHASES.length));
  }

  function start() {
    setElapsedSeconds(0);
    setRunning(true);
    runningRef.current = true;
    runPhase(0);
  }

  function stop() {
    setRunning(false);
    runningRef.current = false;
    scaleAnim.stopAnimation();
    scaleAnim.setValue(1);
  }

  if (running) {
    return (
      <View style={styles.activeContainer}>
        <Stack.Screen options={{ headerShown: true, title: 'Respiration', headerBackTitle: 'Retour' }} />
        <Animated.View style={[styles.circle, { transform: [{ scale: scaleAnim }] }]} />
        <Text style={styles.phaseLabel}>{PHASES[phaseIndex].label}</Text>
        <Pressable style={styles.stopButton} onPress={stop}>
          <Text style={styles.stopButtonText}>Arrêter</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ headerShown: true, title: 'Respiration', headerBackTitle: 'Retour' }} />
      <Text style={styles.subtitle}>
        Quelques minutes de respiration carrée pour redescendre en tension — pas besoin d'attendre une vraie pause pour l'utiliser.
      </Text>

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

      <Pressable style={styles.startButton} onPress={start}>
        <Text style={styles.startButtonText}>Commencer</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing.lg },
  subtitle: { ...typography.body, color: colors.textMuted, marginBottom: spacing.xl },
  durationLabel: { ...typography.caption, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: spacing.xs },
  durationRow: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.xl },
  durationChip: { borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingVertical: 6, paddingHorizontal: spacing.md },
  durationChipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
  durationText: { fontSize: 13, color: colors.textMuted },
  durationTextActive: { color: colors.primary, fontFamily: fonts.semibold },
  startButton: { backgroundColor: colors.primary, borderRadius: 12, padding: spacing.md, alignItems: 'center' },
  startButtonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 16 },
  activeContainer: { flex: 1, backgroundColor: colors.background, justifyContent: 'center', alignItems: 'center', padding: spacing.lg },
  circle: { width: 160, height: 160, borderRadius: 80, backgroundColor: colors.primaryMuted, marginBottom: spacing.xl },
  phaseLabel: { ...typography.title, marginBottom: spacing.xl },
  stopButton: { borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingVertical: spacing.md, paddingHorizontal: spacing.xl },
  stopButtonText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 16 },
});
