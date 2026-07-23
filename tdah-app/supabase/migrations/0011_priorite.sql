-- Niveau de priorité (Haute/Moyenne/Basse), distinct du niveau d'angoisse —
-- l'angoisse mesure la difficulté émotionnelle, la priorité mesure
-- l'urgence/importance. Inspiré du triage Haute/Moyenne/Basse vu dans les
-- captures Tiimo (leur "Co-planner" trie automatiquement par IA ; on garde
-- la version manuelle, plus simple et sans coût d'appel IA).

alter table public.tasks
  add column niveau_priorite text check (niveau_priorite in ('haute', 'moyenne', 'basse'));
