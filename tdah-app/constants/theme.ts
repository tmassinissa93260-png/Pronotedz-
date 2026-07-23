// Palette volontairement calme et peu saturée : le public TDAH est déjà en
// surcharge sensorielle une bonne partie du temps, l'app ne doit pas en rajouter.
// La couleur vive reste réservée à de petites touches (bouton, badge, drapeau)
// sur un fond neutre à faible saturation (~30%) — jamais en grande surface —
// conformément à la littérature UX sur le TDAH qui déconseille la saturation
// ambiante (recherche associée aux interventions "écran en niveaux de gris").
export const lightColors = {
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

// Mode sombre : noir bleu nuit — pas un noir plat façon Tiimo (qui perd tout
// relief entre les cartes et le fond), et pas non plus de noir pur (halation/
// éblouissement plus fort en faible luminosité, inconfortable en usage
// prolongé). La base est un anthracite à dominante bleu nuit plutôt que
// violette : le bleu nuit lit plus "calme, nuit, sommeil" — cohérent avec un
// compagnon qu'on ouvre aussi le soir — tandis que l'indigo de la marque,
// légèrement rafraîchi vers le bleu, garde son identité sans détonner dessus.
export const darkColors = {
  background: '#0A0D16',
  surface: '#12151F',
  surfaceAlt: '#1B2032',
  border: '#262C40',
  primary: '#7C82F0',
  primaryDark: '#5F63D6',
  primaryMuted: '#232A4A',
  accent: '#F0A47E',
  accentMuted: '#332720',
  text: '#ECEFF8',
  textMuted: '#8891AC',
  success: '#57C08A',
  successMuted: '#1B3327',
  warning: '#E8A85C',
  danger: '#EA6F68',
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
  md: 14,
  lg: 20,
  xl: 26,
  pill: 999,
};

// Ombre douce et cohérente pour toutes les cartes/panneaux flottants —
// c'est ce qui donne la sensation de profondeur "app moderne 2026" plutôt
// que le plat bordure-seule qu'on avait avant. Les ombres portées étant peu
// visibles sur fond sombre de toute façon, on garde une seule définition.
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
// cohérent avec le ton bienveillant de l'app. Reste la seule famille pour
// tout ce qui est fonctionnel (boutons, corps de texte, étiquettes) : c'est
// elle qui porte la lisibilité au quotidien.
//
// Fraunces (serif) vient seulement sur le titre de chaque écran principal —
// exactement où Tiimo la réserve elle-même ("Jeudi", "Concentration", "À
// faire"). Le pairing serif/grotesque est ce qui donne à une app l'air
// "designée" plutôt que gabarit générique ; l'utiliser partout diluerait cet
// effet, d'où la retenue à un seul point d'usage par écran.
export const fonts = {
  regular: 'Manrope_400Regular',
  medium: 'Manrope_500Medium',
  semibold: 'Manrope_600SemiBold',
  bold: 'Manrope_700Bold',
  extrabold: 'Manrope_800ExtraBold',
  displaySemibold: 'Fraunces_600SemiBold',
};

// Espacement généreux plutôt que resserré : la recherche sur la lecture chez
// les personnes TDAH montre que l'espacement (interlignage, tracking) pèse
// plus lourd que la forme des lettres elle-même sur la charge cognitive —
// donc pas de letterSpacing négatif façon "logo", même sur le titre, et un
// line-height nettement supérieur à la taille de police par défaut.
export function makeTypography(c: ThemeColors) {
  return {
    title: { fontSize: 32, lineHeight: 39, fontFamily: fonts.displaySemibold, color: c.text, letterSpacing: 0 },
    heading: { fontSize: 20, lineHeight: 27, fontFamily: fonts.bold, color: c.text },
    body: { fontSize: 16, lineHeight: 24, fontFamily: fonts.regular, color: c.text },
    caption: { fontSize: 13, lineHeight: 19, fontFamily: fonts.medium, color: c.textMuted, letterSpacing: 0.1 },
  };
}

export const typography = makeTypography(lightColors);
