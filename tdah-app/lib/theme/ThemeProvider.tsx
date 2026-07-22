import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { useColorScheme } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { lightColors, darkColors, makeTypography, shadow, spacing, radius, fonts, type ThemeColors } from '../../constants/theme';

export type ThemePreference = 'system' | 'light' | 'dark';
const STORAGE_KEY = 'theme_preference';

type ThemeContextValue = {
  scheme: 'light' | 'dark';
  colors: ThemeColors;
  typography: ReturnType<typeof makeTypography>;
  spacing: typeof spacing;
  radius: typeof radius;
  shadow: typeof shadow;
  fonts: typeof fonts;
  preference: ThemePreference;
  setPreference: (p: ThemePreference) => void;
};

const light = { scheme: 'light' as const, colors: lightColors, typography: makeTypography(lightColors), spacing, radius, shadow, fonts };
const ThemeContext = createContext<ThemeContextValue>({ ...light, preference: 'system', setPreference: () => {} });

export function ThemeProvider({ children }: PropsWithChildren) {
  const systemScheme = useColorScheme();
  const [preference, setPreferenceState] = useState<ThemePreference>('system');

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY).then((v) => {
      if (v === 'light' || v === 'dark' || v === 'system') setPreferenceState(v);
    });
  }, []);

  function setPreference(p: ThemePreference) {
    setPreferenceState(p);
    AsyncStorage.setItem(STORAGE_KEY, p);
  }

  const scheme: 'light' | 'dark' = preference === 'system' ? (systemScheme === 'dark' ? 'dark' : 'light') : preference;

  const value = useMemo<ThemeContextValue>(() => {
    const activeColors = scheme === 'dark' ? darkColors : lightColors;
    return {
      scheme,
      colors: activeColors,
      typography: makeTypography(activeColors),
      spacing,
      radius,
      shadow,
      fonts,
      preference,
      setPreference,
    };
  }, [scheme, preference]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
