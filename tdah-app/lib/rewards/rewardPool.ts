// Récompense à variance plutôt qu'à montant/forme fixe : un signal identique
// à chaque fois perd son effet dopaminergique par habituation (modèle de
// Tripp & Wickens sur le TDAH). On fait varier la NATURE du signal, pas
// juste son intensité — et parfois, volontairement, presque rien.

export type Reward = { emoji: string; text: string; subtle: boolean };

const REWARDS: Reward[] = [
  { emoji: '✨', text: 'Nice.', subtle: false },
  { emoji: '🌱', text: 'Ça compte.', subtle: false },
  { emoji: '👏', text: 'T’as géré.', subtle: false },
  { emoji: '🔥', text: 'Allez, suivant.', subtle: false },
  { emoji: '', text: 'Fait.', subtle: true },
  { emoji: '💪', text: 'Une de plus.', subtle: false },
  { emoji: '🎯', text: 'Dans le mille.', subtle: false },
  { emoji: '', text: '', subtle: true }, // parfois, rien de spectaculaire — c'est voulu
];

export function pickReward(gamificationPref: string): Reward | null {
  if (gamificationPref === 'off') return null;

  if (gamificationPref === 'discrete') {
    const subtleOnly = REWARDS.filter((r) => r.subtle || r.emoji === '✨' || r.emoji === '🌱');
    return subtleOnly[Math.floor(Math.random() * subtleOnly.length)];
  }

  return REWARDS[Math.floor(Math.random() * REWARDS.length)];
}
