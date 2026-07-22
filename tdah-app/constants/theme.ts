// Palette volontairement calme et peu saturée : le public TDAH est déjà en
// surcharge sensorielle une bonne partie du temps, l'app ne doit pas en rajouter.
export const colors = {
  background: '#FAF9F6',
  surface: '#FFFFFF',
  border: '#E4E1DA',
  primary: '#5B6EE8',
  primaryMuted: '#EEF0FD',
  text: '#1F2333',
  textMuted: '#6B7080',
  success: '#4B9B6E',
  warning: '#D98A3D',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
};

export const typography = {
  title: { fontSize: 28, fontWeight: '700' as const, color: colors.text },
  heading: { fontSize: 20, fontWeight: '600' as const, color: colors.text },
  body: { fontSize: 16, fontWeight: '400' as const, color: colors.text },
  caption: { fontSize: 13, fontWeight: '400' as const, color: colors.textMuted },
};
