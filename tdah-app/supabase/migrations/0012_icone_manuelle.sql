-- Personnalisation manuelle de l'icône/couleur d'une tâche (façon Tiimo,
-- "3000+ couleurs et icônes"). L'auto-détection par mots-clés (lib/taskIcon.ts)
-- reste le comportement par défaut ; ces colonnes permettent de la
-- surcharger tâche par tâche.

alter table public.tasks
  add column icone_manuelle text,
  add column couleur_manuelle text;
