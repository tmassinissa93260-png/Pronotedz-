-- Chronothérapie sommeil (V1 en saisie manuelle) + check-in "humeur" —
-- la synchronisation automatique Apple Watch/Health Connect reste bloquée
-- par Expo Go (module natif, nécessiterait un build EAS), donc on démarre
-- avec une saisie manuelle : ça marche dès aujourd'hui, et la table
-- wearable_data existante est déjà prête à recevoir une vraie synchro plus
-- tard sans migration supplémentaire (colonne source déjà générique).

alter table public.wearable_data
  drop constraint wearable_data_source_check,
  add constraint wearable_data_source_check
    check (source in ('apple_watch', 'oura', 'whoop', 'manuel', 'autre'));

alter table public.checkins
  drop constraint checkins_type_check,
  add constraint checkins_type_check
    check (type in ('faim', 'fatigue', 'toilettes', 'humeur', 'autre'));
