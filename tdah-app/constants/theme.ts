// Palette volontairement calme et peu saturée : le public TDAH est déjà en
// surcharge sensorielle une bonne partie du temps, l'app ne doit pas en rajouter.
// La couleur vive reste réservée à de petites touches (bouton, badge, drapeau)
// sur un fond neutre à faible saturation (~30%) — jamais en grande surface —
// conformément à la littérature UX sur le TDAH qui déconseille la saturation
// ambiante (recherche associée aux interventions "écran en niveaux de gris").
export const colors = {
  background: '#F8F6F2',
  surface: '#FFFFFF',
  surfaceAlt: '#F1EFFC',
  border: '#EAE6DD',
  primary: '#5B4FE8',
  primaryDark: '#4A3FCB',
  primaryMuted: '#EEEBFC',
  accent: '#ED946E',
  accentMuted: '#FBEEE6',
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

// Espacement généreux plutôt que resserré : la recherche sur la lecture chez
// les personnes TDAH montre que l'espacement (interlignage, tracking) pèse
// plus lourd que la forme des lettres elle-même sur la charge cognitive —
// donc pas de letterSpacing négatif façon "logo", même sur le titre, et un
// line-height nettement supérieur à la taille de police par défaut.
export const typography = {
  title: { fontSize: 28, lineHeight: 36, fontFamily: fonts.extrabold, color: colors.text, letterSpacing: 0.1 },
  heading: { fontSize: 20, lineHeight: 27, fontFamily: fonts.bold, color: colors.text },
  body: { fontSize: 16, lineHeight: 24, fontFamily: fonts.regular, color: colors.text },
  caption: { fontSize: 13, lineHeight: 19, fontFamily: fonts.medium, color: colors.textMuted, letterSpacing: 0.1 },
};
