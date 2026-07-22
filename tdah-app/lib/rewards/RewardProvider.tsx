import { createContext, useCallback, useContext, useRef, useState, type PropsWithChildren } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import { pickReward, type Reward } from './rewardPool';
import { colors, spacing } from '../../constants/theme';

type RewardContextValue = {
  celebrate: (gamificationPref: string) => void;
};

const RewardContext = createContext<RewardContextValue>({ celebrate: () => {} });

export function RewardProvider({ children }: PropsWithChildren) {
  const [current, setCurrent] = useState<Reward | null>(null);
  const opacity = useRef(new Animated.Value(0)).current;

  const celebrate = useCallback(
    (gamificationPref: string) => {
      const reward = pickReward(gamificationPref);
      if (!reward || (!reward.text && !reward.emoji)) return; // le "rien" fait aussi partie du cycle

      setCurrent(reward);
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

const styles = StyleSheet.create({
  toast: {
    position: 'absolute',
    top: 80,
    alignSelf: 'center',
    backgroundColor: colors.primary,
    borderRadius: 20,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  toastText: { color: '#fff', fontSize: 15, fontWeight: '600' },
});
