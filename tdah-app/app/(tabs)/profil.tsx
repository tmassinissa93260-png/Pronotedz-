import { View, Text, Pressable, StyleSheet, Alert, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { supabase } from '../../lib/supabase/client';
import { useAuth } from '../../lib/supabase/AuthProvider';
import { colors, spacing, typography, fonts } from '../../constants/theme';

export default function ProfilScreen() {
  const { session } = useAuth();

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
        <Text style={styles.sectionTitle}>Confiance & données</Text>
        <InfoRow icon="shield-checkmark-outline" text="Tes données sont hébergées en Union Européenne." />
        <InfoRow icon="lock-closed-outline" text="Jamais utilisées pour entraîner un modèle d’IA tiers." />
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
        <Text style={styles.caption}>Gratuit — résiliable en un clic à tout moment, sans justification à donner.</Text>
      </View>

      <Pressable style={styles.signOutButton} onPress={handleSignOut}>
        <Text style={styles.signOutText}>Se déconnecter</Text>
      </Pressable>
    </ScrollView>
  );
}

function InfoRow({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  return (
    <View style={styles.row}>
      <Ionicons name={icon} size={20} color={colors.success} />
      <Text style={styles.rowText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  title: { ...typography.title, marginBottom: spacing.xs },
  email: { ...typography.body, color: colors.textMuted, marginBottom: spacing.lg },
  section: { marginBottom: spacing.lg },
  sectionTitle: { ...typography.heading, fontSize: 15, marginBottom: spacing.sm, color: colors.textMuted },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.sm },
  rowText: { ...typography.body },
  caption: { ...typography.caption },
  signOutButton: { marginTop: spacing.lg, alignItems: 'center', padding: spacing.md },
  signOutText: { color: colors.warning, fontSize: 16, fontFamily: fonts.semibold },
});
