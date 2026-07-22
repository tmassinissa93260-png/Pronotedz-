import { useEffect, useState } from 'react';
import { supabase } from './client';
import { useAuth } from './AuthProvider';

export type Profile = {
  chronotype: string;
  profil_masking: string;
  preference_ton: string;
  preference_gamification: string;
};

export function useProfile() {
  const { session } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    if (!session) return;
    supabase
      .from('profiles')
      .select('chronotype, profil_masking, preference_ton, preference_gamification')
      .eq('id', session.user.id)
      .single()
      .then(({ data }) => setProfile(data));
  }, [session]);

  return profile;
}
