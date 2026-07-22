import { Stack, useRouter, useSegments } from 'expo-router';
import { useEffect, useState } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { AuthProvider, useAuth } from '../lib/supabase/AuthProvider';
import { supabase } from '../lib/supabase/client';
import { RewardProvider } from '../lib/rewards/RewardProvider';

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

  return <Stack screenOptions={{ headerShown: false }} />;
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <RewardProvider>
          <RootNavigation />
          <StatusBar style="auto" />
        </RewardProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
