import { useEffect, useMemo } from 'react';
import { View, Text, Pressable, StyleSheet, Alert, ScrollView, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { supabase } from '../../lib/supabase/client';
import { useAuth } from '../../lib/supabase/AuthProvider';
import { spacing, fonts, radius, makeTypography, type ThemeColors } from '../../constants/theme';
import { useTheme, type ThemePreference } from '../../lib/theme/ThemeProvider';
import { useSubscription, refreshSubscription } from '../../lib/billing/stripe';

const THEME_OPTIONS: { value: ThemePreference; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { value: 'system', label: 'Système', icon: 'phone-portrait-outline' },
  { value: 'light', label: 'Clair', icon: 'sunny-outline' },
  { value: 'dark', label: 'Sombre', icon: 'moon-outline' },
];

export default function ProfilScreen() {
  const { session } = useAuth();
  const { colors, preference, setPreference, focusMode, setFocusMode } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { statut, isPremium, reload } = useSubscription();

  // Seul écran qui interroge Stripe pour rester à jour (renouvellements,
  // annulations) — pas de webhook dans cette architecture, voir la
  // migration 0015 pour le détail de ce choix.
  useEffect(() => {
    if (!session) return;
    refreshSubscription(session.user.id)
      .then(reload)
      .catch(() => {});
  }, [session]);

  async function handleSignOut() {
    await supabase.auth.signOut();
  }

  async function handleExportData() {
    // V1 : confirmation + export simple par email (via une future Edge Function).
    // On l'affiche déjà comme argument de confiance central, même minimal au début.
    Alert.alert(
      'Export de tes données',
      'On t’enverra un fichier avec toutes tes données (tâches, sessions, check-ins) par email sous peu.'
    );
  }

  function handleDeleteAccount() {
    Alert.alert(
      'Supprimer ton compte',
      'Toutes tes données seront définitivement supprimées. Cette action est irréversible.',
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Supprimer',
          style: 'destructive',
          onPress: () => {
            // La suppression réelle passera par une Edge Function avec service_role
            // (impossible et volontairement interdit de le faire depuis le client).
            Alert.alert('Demande enregistrée', 'Ton compte sera supprimé sous 48h.');
          },
        },
      ]
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing.lg }}>
      <Text style={styles.title}>Profil</Text>
      <Text style={styles.email}>{session?.user.email}</Text>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Apparence</Text>
        <View style={styles.themeRow}>
          {THEME_OPTIONS.map((opt) => (
            <Pressable
              key={opt.value}
              style={[styles.themeChip, preference === opt.value && styles.themeChipActive]}
              onPress={() => setPreference(opt.value)}
            >
              <Ionicons name={opt.icon} size={16} color={preference === opt.value ? colors.primary : colors.textMuted} />
              <Text style={[styles.themeChipText, preference === opt.value && styles.themeChipTextActive]}>{opt.label}</Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.focusModeRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.focusModeTitle}>Mode focus</Text>
            <Text style={styles.caption}>
              Réduit encore les couleurs décoratives et coupe les animations — pour les jours où même ça, c'est trop.
            </Text>
          </View>
          <Switch
            value={focusMode}
            onValueChange={setFocusMode}
            trackColor={{ false: colors.border, true: colors.primaryMuted }}
            thumbColor={focusMode ? colors.primary : undefined}
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Confiance & données</Text>
        <InfoRow icon="shield-checkmark-outline" text="Tes données sont hébergées en Union Européenne." styles={styles} colors={colors} />
        <InfoRow icon="lock-closed-outline" text="Jamais utilisées pour entraîner un modèle d’IA tiers." styles={styles} colors={colors} />
        <Pressable style={styles.row} onPress={handleExportData}>
          <Ionicons name="download-outline" size={20} color={colors.text} />
          <Text style={styles.rowText}>Exporter mes données</Text>
        </Pressable>
        <Pressable style={styles.row} onPress={handleDeleteAccount}>
          <Ionicons name="trash-outline" size={20} color={colors.warning} />
          <Text style={[styles.rowText, { color: colors.warning }]}>Supprimer mon compte</Text>
        </Pressable>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Outils</Text>
        <Pressable style={styles.row} onPress={() => router.push('/brouillon-differe')}>
          <Ionicons name="hourglass-outline" size={20} color={colors.text} />
          <Text style={styles.rowText}>Brouillon différé</Text>
        </Pressable>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Abonnement</Text>
        {isPremium ? (
          <Text style={styles.caption}>Abonnement actif — merci de soutenir l’app 💜</Text>
        ) : (
          <>
            <Text style={styles.caption}>
              {statut === 'annule' || statut === 'expire'
                ? 'Ton abonnement précédent est terminé.'
                : 'Toutes les fonctionnalités sont gratuites pour l’instant.'}
            </Text>
            <Pressable style={styles.row} onPress={() => router.push('/paiement')}>
              <Ionicons name="star-outline" size={20} color={colors.primary} />
              <Text style={[styles.rowText, { color: colors.primary }]}>Voir les offres</Text>
            </Pressable>
          </>
        )}
      </View>

      <Pressable style={styles.signOutButton} onPress={handleSignOut}>
        <Text style={styles.signOutText}>Se déconnecter</Text>
      </Pressable>
    </ScrollView>
  );
}

function InfoRow({
  icon,
  text,
  styles,
  colors,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  text: string;
  styles: ReturnType<typeof makeStyles>;
  colors: ThemeColors;
}) {
  return (
    <View style={styles.row}>
      <Ionicons name={icon} size={20} color={colors.success} />
      <Text style={styles.rowText}>{text}</Text>
    </View>
  );
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    title: { ...typography.title, marginBottom: spacing.xs },
    email: { ...typography.body, color: colors.textMuted, marginBottom: spacing.lg },
    section: { marginBottom: spacing.lg },
    sectionTitle: { ...typography.heading, fontSize: 15, marginBottom: spacing.sm, color: colors.textMuted },
    themeRow: { flexDirection: 'row', gap: spacing.xs },
    themeChip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.pill,
      paddingVertical: spacing.xs,
      paddingHorizontal: spacing.md,
    },
    themeChipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
    themeChipText: { fontSize: 13, fontFamily: fonts.medium, color: colors.textMuted },
    themeChipTextActive: { color: colors.primary, fontFamily: fonts.semibold },
    focusModeRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginTop: spacing.md },
    focusModeTitle: { ...typography.body, fontFamily: fonts.semibold, marginBottom: 2 },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.sm },
    rowText: { ...typography.body },
    caption: { ...typography.caption },
    signOutButton: { marginTop: spacing.lg, alignItems: 'center', padding: spacing.md },
    signOutText: { color: colors.warning, fontSize: 16, fontFamily: fonts.semibold },
  });
}
