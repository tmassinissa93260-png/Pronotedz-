-- Routines récurrentes façon Tiimo : au lieu de ne gérer que des tâches
-- ponctuelles du jour, l'utilisateur peut définir un modèle qui se
-- matérialise automatiquement en tâche du jour les jours choisis. La
-- matérialisation se fait côté client (ensureRoutinesForToday), pas par un
-- job planifié côté serveur, pour rester simple à maintenir sans accès
-- terminal/CLI.

create table public.routines (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  titre text not null,
  moment_journee text not null default 'n_importe_quand'
    check (moment_journee in ('n_importe_quand', 'matin', 'jour', 'soir')),
  estimation_minutes int,
  -- jours de la semaine où la routine s'applique, au format JS Date.getDay()
  -- (0 = dimanche ... 6 = samedi), pour un mapping direct côté client.
  jours int[] not null default '{0,1,2,3,4,5,6}',
  actif boolean not null default true,
  created_at timestamptz not null default now()
);

alter table public.routines enable row level security;

create policy "routines: propriétaire uniquement"
  on public.routines for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

alter table public.tasks
  add column routine_id uuid references public.routines (id) on delete set null;
