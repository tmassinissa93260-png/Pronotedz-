-- Réorganisation manuelle des tâches : la plainte la plus citée sur Tiimo
-- dans les avis App Store est l'impossibilité de déplacer une tâche une
-- fois ajoutée. On ajoute un ordre explicite par tâche (au lieu de se fier
-- uniquement à created_at), modifiable via des flèches haut/bas côté client.

alter table public.tasks
  add column ordre int not null default 0;
