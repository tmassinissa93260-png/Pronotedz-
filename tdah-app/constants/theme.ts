// Palette "sobre et premium" — noir neutre profond plutôt que teinté (bleu nuit
// ou indigo), un seul vert net comme couleur de marque (concentration, calme,
// croissance), et des cartes bien aérées avec ombre neutre plutôt que colorée.
// Reste à faible saturation ambiante (le public TDAH est déjà en surcharge
// sensorielle une bonne partie du temps) — la couleur vive reste réservée à
// de petites touches (bouton, badge, drapeau), jamais en grande surface.
export const lightColors = {
  background: '#F6F7F5',
  surface: '#FFFFFF',
  surfaceAlt: '#EEF2EE',
  border: '#E1E5E0',
  primary: '#15803D',
  primaryDark: '#0F6631',
  primaryMuted: '#E1F5E8',
  accent: '#ED946E',
  accentMuted: '#FBEEE6',
  text: '#14181B',
  textMuted: '#5C665F',
  success: '#15803D',
  successMuted: '#E1F5E8',
  warning: '#C97A2E',
  danger: '#D14A41',
};

// Mode sombre : noir neutre profond — pas de teinte bleu-nuit ni indigo (ça se
// lit vite comme un gabarit SaaS générique), pas non plus de noir pur
// (halation/éblouissement plus fort en faible luminosité). Le vert est
// l'unique couleur de marque — fonctionne aussi bien pour l'accent que pour
// "succès", cohérent avec l'image d'une app de concentration/croissance.
export const darkColors = {
  background: '#0A0C0B',
  surface: '#15181A',
  surfaceAlt: '#1D2321',
  border: '#272E2B',
  primary: '#059669',
  primaryDark: '#047857',
  primaryMuted: '#16301F',
  accent: '#F0A47E',
  accentMuted: '#332720',
  text: '#EEF2EF',
  textMuted: '#8B968F',
  success: '#059669',
  successMuted: '#16301F',
  warning: '#E8A85C',
  danger: '#EF6B61',
};

export type ThemeColors = typeof lightColors;

// "Mode focus" : neutralise les touches de couleur purement décoratives
// (bannière grenouille, badge de série, bulle d'icône de tâche) en réutilisant
// les tokens neutres déjà là — les couleurs fonctionnelles (priorité, succès,
// avertissement, danger) restent intactes, car elles portent une information,
// pas juste de la décoration. Recherche UX-TDAH : la saturation ambiante,
// même par petites touches répétées, ajoute une charge attentionnelle.
export function applyFocusMode(c: ThemeColors): ThemeColors {
  return { ...c, accent: c.textMuted, accentMuted: c.surfaceAlt };
}

// Alias historique : les écrans qui n'ont pas encore été convertis pour lire
// la couleur active via useTheme() continuent d'importer `colors` — ils
// restent volontairement figés en palette claire plutôt que de casser.
export const colors = lightColors;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
};

export const radius = {
  sm: 10,
  md: 16,
  lg: 22,
  xl: 28,
  pill: 999,
};

// Ombre neutre (noir pur, pas teintée) — c'est ce qui donne la sensation de
// profondeur "app premium" plutôt que le plat bordure-seule qu'on avait
// avant, sans réintroduire de teinte colorée dans les zones d'ombre.
export const shadow = {
  card: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.16,
    shadowRadius: 20,
    elevation: 3,
  },
  soft: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 1,
  },
};

// Manrope : géométrique, terminaisons arrondies — moderne sans être froid,
// cohérent avec le ton bienveillant de l'app. Seule famille dans toute
// l'app, y compris les titres (voir makeTypography) : un pairing
// serif/grotesque lisait plus "édito 2018" que "outil premium 2026" — la
// hiérarchie vient maintenant du poids (extrabold) et de la taille, pas
// d'un changement de famille, cohérent avec le fond noir neutre + vert.
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
export function makeTypography(c: ThemeColors) {
  return {
    title: { fontSize: 32, lineHeight: 39, fontFamily: fonts.extrabold, color: c.text, letterSpacing: 0 },
    heading: { fontSize: 20, lineHeight: 27, fontFamily: fonts.bold, color: c.text },
    body: { fontSize: 16, lineHeight: 24, fontFamily: fonts.regular, color: c.text },
    caption: { fontSize: 13, lineHeight: 19, fontFamily: fonts.medium, color: c.textMuted, letterSpacing: 0.1 },
  };
}

export const typography = makeTypography(lightColors);
