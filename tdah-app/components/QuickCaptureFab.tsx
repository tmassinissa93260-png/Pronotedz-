import { useMemo, useRef, useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, Modal, KeyboardAvoidingView, Platform, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '../lib/supabase/AuthProvider';
import { supabase } from '../lib/supabase/client';
import { useTheme } from '../lib/theme/ThemeProvider';
import { spacing, radius, shadow, fonts, makeTypography, makeGradients, type ThemeColors } from '../constants/theme';

// Capture rapide : accessible partout, texte libre, aucun champ obligatoire.
// On range la note dans le backlog du jour (sans horaire) — elle se structure
// après, jamais au moment de la capture.
const today = () => new Date().toISOString().slice(0, 10);

// Maintenance prédictive nocturne : beaucoup de captures d'un coup en pleine
// nuit est un signe classique d'hyperfocus — jamais bloquant, juste un signal
// doux et unique par nuit pour inviter à laisser reposer ces idées. Compteur
// au niveau module (pas du composant) car la capture est désormais globale,
// utilisable depuis n'importe quel écran.
let nightAddCount = 0;
let nightWarned = false;
function signalerAjoutNocturne() {
  if (new Date().getHours() >= 5) return;
  nightAddCount += 1;
  if (nightAddCount < 6 || nightWarned) return;
  nightWarned = true;
  Alert.alert(
    'Le système chauffe 🌙',
    'Beaucoup d’idées d’un coup à cette heure-ci — bon signe d’énergie. Elles sont bien enregistrées ; pense à les relire à tête reposée demain avant de t’y engager.'
  );
}

export default function QuickCaptureFab() {
  const { session } = useAuth();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const gradients = useMemo(() => makeGradients(colors), [colors]);
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [saved, setSaved] = useState(false);
  const inputRef = useRef<TextInput>(null);

  if (!session) return null;

  function close() {
    setOpen(false);
    setText('');
    setSaved(false);
  }

  async function capture() {
    const value = text.trim();
    if (!value || !session) {
      close();
      return;
    }
    setSaved(true);
    await supabase.from('tasks').insert({
      user_id: session.user.id,
      titre: value,
      date_prevue: today(),
    });
    signalerAjoutNocturne();
    setTimeout(close, 600);
  }

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        style={[styles.fabWrap, { bottom: insets.bottom + 84 }]}
        accessibilityLabel="Capture rapide"
        hitSlop={8}
      >
        <LinearGradient colors={gradients.primary} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.fab}>
          <Ionicons name="add" size={28} color="#fff" />
        </LinearGradient>
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={close}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.backdrop}
        >
          <Pressable style={StyleSheet.absoluteFill} onPress={close} />
          <View style={styles.sheet}>
            {saved ? (
              <View style={styles.savedRow}>
                <Ionicons name="checkmark-circle" size={22} color={colors.success} />
                <Text style={styles.savedText}>Noté.</Text>
              </View>
            ) : (
              <>
                <Text style={styles.label}>Capture rapide</Text>
                <TextInput
                  ref={inputRef}
                  autoFocus
                  multiline
                  style={styles.input}
                  placeholder="Une idée, une tâche… écris, on structure après"
                  placeholderTextColor={colors.textMuted}
                  value={text}
                  onChangeText={setText}
                  onSubmitEditing={capture}
                  returnKeyType="done"
                  blurOnSubmit
                />
                <View style={styles.row}>
                  <Pressable onPress={close} style={styles.cancelButton} hitSlop={8}>
                    <Text style={styles.cancelText}>Annuler</Text>
                  </Pressable>
                  <Pressable onPress={capture} hitSlop={8}>
                    <LinearGradient colors={gradients.primary} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.saveButton}>
                      <Ionicons name="arrow-up" size={20} color="#fff" />
                    </LinearGradient>
                  </Pressable>
                </View>
              </>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </>
  );
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
    fabWrap: {
      position: 'absolute',
      right: spacing.lg,
      width: 56,
      height: 56,
      borderRadius: 28,
      ...shadow.card,
      zIndex: 50,
    },
    fab: {
      width: 56,
      height: 56,
      borderRadius: 28,
      alignItems: 'center',
      justifyContent: 'center',
    },
    backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
    sheet: {
      backgroundColor: colors.surface,
      borderTopLeftRadius: radius.lg,
      borderTopRightRadius: radius.lg,
      padding: spacing.lg,
      paddingBottom: spacing.xl,
      minHeight: 160,
      gap: spacing.sm,
    },
    label: { ...typography.caption, color: colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5, fontFamily: fonts.semibold },
    input: {
      ...typography.body,
      color: colors.text,
      minHeight: 60,
      maxHeight: 140,
      fontFamily: fonts.medium,
      fontSize: 17,
    },
    row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: spacing.sm },
    cancelButton: { paddingVertical: spacing.sm, paddingHorizontal: spacing.sm, minHeight: 44, justifyContent: 'center' },
    cancelText: { ...typography.body, color: colors.textMuted, fontFamily: fonts.medium },
    saveButton: {
      width: 44,
      height: 44,
      borderRadius: 22,
      alignItems: 'center',
      justifyContent: 'center',
    },
    savedRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.lg, justifyContent: 'center' },
    savedText: { ...typography.body, color: colors.text, fontFamily: fonts.semibold },
  });
}
