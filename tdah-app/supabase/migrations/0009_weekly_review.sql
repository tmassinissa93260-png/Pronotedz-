-- Bilan hebdomadaire : le rituel de fin de journée existe déjà (0006), on
-- ajoute son équivalent à l'échelle de la semaine — trois questions
-- réflexives, pas une nouvelle page de statistiques (le Dashboard fait déjà
-- ça). Répond au point "bilans hebdomadaires" cité dans les checklists
-- "bonne app" pour la gestion de l'attention.

create table public.weekly_reviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  semaine_debut date not null default current_date,
  points_forts text,
  a_ameliorer text,
  priorite_semaine text,
  created_at timestamptz not null default now(),
  unique (user_id, semaine_debut)
);

alter table public.weekly_reviews enable row level security;

create policy "weekly_reviews: propriétaire uniquement"
  on public.weekly_reviews for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
