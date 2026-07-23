-- Schéma initial — compagnon TDAH
-- Toutes les tables sensibles sont protégées par Row Level Security (RLS) :
-- chaque utilisateur ne peut lire/écrire que ses propres lignes.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- profiles : étend auth.users avec les données d'onboarding
-- ---------------------------------------------------------------------------
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  chronotype text check (chronotype in ('matin', 'soir', 'neutre')) default 'neutre',
  profil_masking text check (profil_masking in ('faible', 'moyen', 'eleve')) default 'moyen',
  preference_ton text check (preference_ton in ('direct', 'doux', 'humoristique')) default 'doux',
  preference_gamification text check (preference_gamification in ('intense', 'discrete', 'off')) default 'discrete',
  onboarding_complete boolean not null default false,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "profiles: lecture de son propre profil"
  on public.profiles for select
  using (auth.uid() = id);

create policy "profiles: modification de son propre profil"
  on public.profiles for update
  using (auth.uid() = id);

create policy "profiles: création de son propre profil"
  on public.profiles for insert
  with check (auth.uid() = id);

-- Crée automatiquement la ligne profile à l'inscription.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id) values (new.id);
  insert into public.streaks (user_id) values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ---------------------------------------------------------------------------
-- tasks + sous-tâches générées par l'IA
-- ---------------------------------------------------------------------------
create table public.tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  titre text not null,
  description text,
  statut text not null check (statut in ('a_faire', 'en_cours', 'fait', 'reporte')) default 'a_faire',
  date_prevue date not null default current_date,
  estimation_minutes int,
  temps_reel_minutes int,
  created_at timestamptz not null default now()
);

create index tasks_user_date_idx on public.tasks (user_id, date_prevue);

alter table public.tasks enable row level security;

create policy "tasks: propriétaire uniquement"
  on public.tasks for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create table public.subtasks (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.tasks (id) on delete cascade,
  titre text not null,
  ordre int not null default 0,
  fait boolean not null default false
);

alter table public.subtasks enable row level security;

create policy "subtasks: via la tâche parente"
  on public.subtasks for all
  using (exists (select 1 from public.tasks t where t.id = task_id and t.user_id = auth.uid()))
  with check (exists (select 1 from public.tasks t where t.id = task_id and t.user_id = auth.uid()));

-- ---------------------------------------------------------------------------
-- sessions de body doubling
-- ---------------------------------------------------------------------------
create table public.sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  type text not null check (type in ('responsabilisation', 'coregulation')),
  partenaire text not null default 'ia', -- 'ia' ou uuid d'un autre utilisateur (V2 communautaire)
  duree_minutes int,
  started_at timestamptz not null default now(),
  ended_at timestamptz
);

alter table public.sessions enable row level security;

create policy "sessions: propriétaire uniquement"
  on public.sessions for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- check-ins d'interoception
-- ---------------------------------------------------------------------------
create table public.checkins (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  type text not null check (type in ('faim', 'fatigue', 'toilettes', 'autre')),
  reponse text not null,
  contexte_declencheur text,
  created_at timestamptz not null default now()
);

alter table public.checkins enable row level security;

create policy "checkins: propriétaire uniquement"
  on public.checkins for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- streaks (avec réparation, pas de rupture punitive)
-- ---------------------------------------------------------------------------
create table public.streaks (
  user_id uuid primary key references auth.users (id) on delete cascade,
  jours_consecutifs int not null default 0,
  reparations_disponibles int not null default 2,
  derniere_activite date
);

alter table public.streaks enable row level security;

create policy "streaks: propriétaire uniquement"
  on public.streaks for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- pattern_memory (V2 — la table existe dès maintenant, l'analyse arrive plus
-- tard une fois assez d'historique accumulé dans tasks/checkins/sessions)
-- ---------------------------------------------------------------------------
create table public.pattern_memory (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  pattern_detecte text not null,
  confiance numeric check (confiance between 0 and 1),
  updated_at timestamptz not null default now()
);

alter table public.pattern_memory enable row level security;

create policy "pattern_memory: propriétaire uniquement"
  on public.pattern_memory for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- wearable_data (V2 — pipeline de collecte branché dès le MVP, coaching
-- basé dessus activé plus tard une fois assez de données)
-- ---------------------------------------------------------------------------
create table public.wearable_data (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  source text not null check (source in ('apple_watch', 'oura', 'whoop', 'autre')),
  hrv numeric,
  sommeil_minutes int,
  sommeil_qualite numeric,
  recorded_at timestamptz not null default now()
);

alter table public.wearable_data enable row level security;

create policy "wearable_data: propriétaire uniquement"
  on public.wearable_data for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
