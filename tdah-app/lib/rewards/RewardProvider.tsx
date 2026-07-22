import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react';
import { AccessibilityInfo, Animated, StyleSheet, Text } from 'react-native';
import { pickReward, type Reward } from './rewardPool';
import { spacing, fonts, type ThemeColors } from '../../constants/theme';
import { useTheme } from '../theme/ThemeProvider';

type RewardContextValue = {
  celebrate: (gamificationPref: string) => void;
};

const RewardContext = createContext<RewardContextValue>({ celebrate: () => {} });

export function RewardProvider({ children }: PropsWithChildren) {
  const [current, setCurrent] = useState<Reward | null>(null);
  const opacity = useRef(new Animated.Value(0)).current;
  const reduceMotion = useRef(false);
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  // Respecte le réglage "Réduire les animations" du téléphone — l'animation
  // (même discrète) peut capter l'attention de façon disproportionnée chez
  // les personnes TDAH (recherche WCAG sur le mouvement et le TDAH).
  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled?.().then((v) => {
      reduceMotion.current = v;
    });
    const sub = AccessibilityInfo.addEventListener?.('reduceMotionChanged', (v) => {
      reduceMotion.current = v;
    });
    return () => sub?.remove?.();
  }, []);

  const celebrate = useCallback(
    (gamificationPref: string) => {
      const reward = pickReward(gamificationPref);
      if (!reward || (!reward.text && !reward.emoji)) return; // le "rien" fait aussi partie du cycle

      setCurrent(reward);
      if (reduceMotion.current) {
        opacity.setValue(1);
        const timer = setTimeout(() => setCurrent(null), 1300);
        return () => clearTimeout(timer);
      }
      opacity.setValue(0);
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
        Animated.delay(1100),
        Animated.timing(opacity, { toValue: 0, duration: 300, useNativeDriver: true }),
      ]).start(() => setCurrent(null));
    },
    [opacity]
  );

  return (
    <RewardContext.Provider value={{ celebrate }}>
      {children}
      {current && (
        <Animated.View pointerEvents="none" style={[styles.toast, { opacity }]}>
          <Text style={styles.toastText}>
            {current.emoji} {current.text}
          </Text>
        </Animated.View>
      )}
    </RewardContext.Provider>
  );
}

export function useReward() {
  return useContext(RewardContext);
}

function makeStyles(colors: ThemeColors) {
  return StyleSheet.create({
    toast: {
      position: 'absolute',
      top: 80,
      alignSelf: 'center',
      backgroundColor: colors.primary,
      borderRadius: 20,
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.lg,
    },
    toastText: { color: '#fff', fontSize: 15, fontFamily: fonts.semibold },
  });
}
