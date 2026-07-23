import { Stack, useRouter, useSegments } from 'expo-router';
import { useEffect, useState } from 'react';
import { View, ActivityIndicator } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { useFonts, Manrope_400Regular, Manrope_500Medium, Manrope_600SemiBold, Manrope_700Bold, Manrope_800ExtraBold } from '@expo-google-fonts/manrope';
import { AuthProvider, useAuth } from '../lib/supabase/AuthProvider';
import { supabase } from '../lib/supabase/client';
import { RewardProvider } from '../lib/rewards/RewardProvider';
import { ThemeProvider, useTheme } from '../lib/theme/ThemeProvider';
import { colors } from '../constants/theme';
import QuickCaptureFab from '../components/QuickCaptureFab';

function RootNavigation() {
  const { session, isLoading } = useAuth();
  const segments = useSegments();
  const router = useRouter();
  const [onboardingComplete, setOnboardingComplete] = useState<boolean | null>(null);

  useEffect(() => {
    if (!session) {
      setOnboardingComplete(null);
      return;
    }
    supabase
      .from('profiles')
      .select('onboarding_complete')
      .eq('id', session.user.id)
      .single()
      .then(({ data }) => setOnboardingComplete(data?.onboarding_complete ?? false));
  }, [session]);

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';
    const inOnboarding = segments[0] === 'onboarding';

    if (!session && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (session && inAuthGroup) {
      router.replace('/(tabs)');
    } else if (session && onboardingComplete === false && !inOnboarding) {
      router.replace('/onboarding');
    } else if (session && onboardingComplete === true && inOnboarding) {
      router.replace('/(tabs)');
    }
  }, [session, isLoading, segments, onboardingComplete]);

  const segmentList = segments as string[];
  const showCapture =
    !!session && onboardingComplete === true && segmentList[0] !== '(auth)' && segmentList[0] !== 'onboarding' && segmentList[1] !== 'focus';

  return (
    <View style={{ flex: 1 }}>
      <Stack screenOptions={{ headerShown: false }} />
      {showCapture && <QuickCaptureFab />}
    </View>
  );
}

function ThemedApp() {
  const { scheme } = useTheme();
  return (
    <>
      <AuthProvider>
        <RewardProvider>
          <RootNavigation />
        </RewardProvider>
      </AuthProvider>
      <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
    </>
  );
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    Manrope_400Regular,
    Manrope_500Medium,
    Manrope_600SemiBold,
    Manrope_700Bold,
    Manrope_800ExtraBold,
  });

  if (!fontsLoaded) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <ThemedApp />
      </ThemeProvider>
    </SafeAreaProvider>
  );
}
