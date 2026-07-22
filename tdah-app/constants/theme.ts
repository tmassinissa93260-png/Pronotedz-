// Palette volontairement calme et peu saturée : le public TDAH est déjà en
// surcharge sensorielle une bonne partie du temps, l'app ne doit pas en rajouter.
// Reste vrai avec cette version : on affine (indigo plus vivant, accent chaud
// pour les moments positifs) sans jamais monter la saturation globale.
export const colors = {
  background: '#F8F6F2',
  surface: '#FFFFFF',
  surfaceAlt: '#F1EFFC',
  border: '#EAE6DD',
  primary: '#5B4FE8',
  primaryDark: '#4A3FCB',
  primaryMuted: '#EEEBFC',
  accent: '#FF9466',
  accentMuted: '#FFEEE4',
  text: '#1C1B29',
  textMuted: '#6D6B80',
  success: '#3FA672',
  successMuted: '#E4F5EC',
  warning: '#E0923F',
  danger: '#E0564F',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
};

export const radius = {
  sm: 10,
  md: 14,
  lg: 20,
  xl: 26,
  pill: 999,
};

// Ombre douce et cohérente pour toutes les cartes/panneaux flottants —
// c'est ce qui donne la sensation de profondeur "app moderne 2026" plutôt
// que le plat bordure-seule qu'on avait avant.
export const shadow = {
  card: {
    shadowColor: '#332B7A',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 3,
  },
  soft: {
    shadowColor: '#332B7A',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 1,
  },
};

// Manrope : géométrique, terminaisons arrondies — moderne sans être froid,
// cohérent avec le ton bienveillant de l'app. Une seule famille, plusieurs
// graisses, pour rester simple à maintenir sur tous les écrans.
export const fonts = {
  regular: 'Manrope_400Regular',
  medium: 'Manrope_500Medium',
  semibold: 'Manrope_600SemiBold',
  bold: 'Manrope_700Bold',
  extrabold: 'Manrope_800ExtraBold',
};

export const typography = {
  title: { fontSize: 28, fontFamily: fonts.extrabold, color: colors.text, letterSpacing: -0.4 },
  heading: { fontSize: 20, fontFamily: fonts.bold, color: colors.text },
  body: { fontSize: 16, fontFamily: fonts.regular, color: colors.text },
  caption: { fontSize: 13, fontFamily: fonts.medium, color: colors.textMuted },
};
