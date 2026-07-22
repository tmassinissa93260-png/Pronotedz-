// Icône colorée par tâche (façon Tiimo) — plutôt qu'une colonne DB et un
// sélecteur manuel, on devine l'icône à partir de mots-clés dans le titre.
// Gratuit, instantané, et couvre l'immense majorité des tâches du quotidien.

const RULES: { keywords: string[]; emoji: string; color: string }[] = [
  { keywords: ['appel', 'téléphon', 'coup de fil'], emoji: '📞', color: '#E8D9F4' },
  { keywords: ['médicament', 'pilule', 'traitement', 'ordonnance'], emoji: '💊', color: '#F4D9DC' },
  { keywords: ['déjeuner', 'dîner', 'manger', 'repas', 'cuisine', 'cuisiner'], emoji: '🍽️', color: '#D9F4E1' },
  { keywords: ['petit déjeuner', 'petit-déjeuner'], emoji: '☕', color: '#F4EBD9' },
  { keywords: ['course', 'supermarché', 'shopping'], emoji: '🛒', color: '#D9EAF4' },
  { keywords: ['lessive', 'linge', 'ménage', 'ranger', 'nettoyer'], emoji: '🧺', color: '#F4E9D9' },
  { keywords: ['travail', 'bureau', 'réunion', 'meeting', 'email', 'mail'], emoji: '💻', color: '#E1D9F4' },
  { keywords: ['sport', 'gym', 'course à pied', 'muscu', 'vélo'], emoji: '🏃', color: '#D9F4EE' },
  { keywords: ['enfant', 'école', 'crèche'], emoji: '🎒', color: '#F4DCD9' },
  { keywords: ['banque', 'facture', 'impôt', 'compte', 'argent', 'payer'], emoji: '💰', color: '#F4F0D9' },
  { keywords: ['dentiste', 'médecin', 'rendez-vous', 'rdv'], emoji: '🩺', color: '#D9E4F4' },
  { keywords: ['douche', 'toilette', 'hygiène'], emoji: '🚿', color: '#D9F0F4' },
  { keywords: ['lire', 'lecture', 'livre'], emoji: '📖', color: '#EEE1F4' },
  { keywords: ['dormir', 'sommeil', 'sieste', 'repos', 'détente'], emoji: '😴', color: '#DCD9F4' },
];

const DEFAULT_ICON = { emoji: '📝', color: '#E4E1DA' };

export function guessTaskIcon(titre: string): { emoji: string; color: string } {
  const lower = titre.toLowerCase();
  for (const rule of RULES) {
    if (rule.keywords.some((k) => lower.includes(k))) {
      return { emoji: rule.emoji, color: rule.color };
    }
  }
  return DEFAULT_ICON;
}
