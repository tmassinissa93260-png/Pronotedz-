import { View, Text, StyleSheet } from 'react-native';
import { spacing, makeTypography, type ThemeColors } from '../constants/theme';

// Heatmap façon GitHub contributions, mais volontairement sans notion de
// "trou = échec" : une case vide est juste vide, jamais rouge ni alarmante —
// cohérent avec le système de streak à réparation déjà en place.

const WEEKS = 12;
const DAYS = WEEKS * 7;
const SQUARE = 11;

function colorForCount(colors: ThemeColors, count: number) {
  if (count <= 0) return colors.border;
  if (count === 1) return `${colors.primary}40`;
  if (count === 2) return `${colors.primary}80`;
  if (count <= 4) return `${colors.primary}C0`;
  return colors.primary;
}

export function StreakHeatmap({ countsByDate, colors }: { countsByDate: Record<string, number>; colors: ThemeColors }) {
  const typography = makeTypography(colors);
  const today = new Date();
  const days: { date: string; count: number }[] = [];
  for (let i = DAYS - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    days.push({ date: key, count: countsByDate[key] ?? 0 });
  }

  const columns: { date: string; count: number }[][] = [];
  for (let i = 0; i < WEEKS; i++) {
    columns.push(days.slice(i * 7, i * 7 + 7));
  }

  const activeDays = days.filter((d) => d.count > 0).length;

  return (
    <View>
      <View style={styles.grid}>
        {columns.map((col, i) => (
          <View key={i} style={styles.column}>
            {col.map((d) => (
              <View key={d.date} style={[styles.square, { backgroundColor: colorForCount(colors, d.count) }]} />
            ))}
          </View>
        ))}
      </View>
      <Text style={[typography.caption, { marginTop: spacing.sm }]}>
        {activeDays} jour{activeDays > 1 ? 's' : ''} actif{activeDays > 1 ? 's' : ''} sur les {WEEKS} dernières semaines.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', gap: 3 },
  column: { gap: 3 },
  square: { width: SQUARE, height: SQUARE, borderRadius: 3 },
});
