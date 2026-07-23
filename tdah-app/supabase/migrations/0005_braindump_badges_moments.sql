-- Fonctionnalités inspirées de l'analyse de Tiimo (captures App Store) :
-- regroupement par moment de journée, planification IA depuis un "brain
-- dump" en langage libre, et système de badges à collectionner.

-- ---------------------------------------------------------------------------
-- moment_journee sur les tâches : "n'importe quand" vs un créneau du jour.
-- ---------------------------------------------------------------------------
alter table public.tasks
  add column moment_journee text not null default 'n_importe_quand'
    check (moment_journee in ('n_importe_quand', 'matin', 'jour', 'soir')),
  add column heure_debut time;

-- ---------------------------------------------------------------------------
-- Badges à collectionner (façon Tiimo/Finch/Habitica) — au lieu du toast
-- éphémère uniquement, certains jalons débloquent un badge permanent.
-- ---------------------------------------------------------------------------
create table public.badges (
  code text primary key,
  titre text not null,
  description text not null,
  emoji text not null
);

insert into public.badges (code, titre, description, emoji) values
  ('premiere_tache', 'Premier pas', 'Ta toute première tâche terminée.', '🌱'),
  ('streak_7', 'Une semaine tenue', '7 jours d''activité d''affilée.', '🔥'),
  ('streak_30', 'Un mois solide', '30 jours d''activité d''affilée.', '🏆'),
  ('sessions_10', 'Habitué du focus', '10 sessions de body doubling terminées.', '🎯'),
  ('reparation_utilisee', 'Ça arrive à tout le monde', 'Première réparation de série utilisée — pas de honte.', '🩹'),
  ('braindump_premier', 'Vide-tête réussi', 'Premier planning généré depuis un brain dump.', '🧠')
on conflict (code) do nothing;

create table public.user_badges (
  user_id uuid not null references auth.users (id) on delete cascade,
  badge_code text not null references public.badges (code),
  obtenu_le timestamptz not null default now(),
  primary key (user_id, badge_code)
);

alter table public.user_badges enable row level security;

create policy "user_badges: lecture de ses propres badges"
  on public.user_badges for select
  using (auth.uid() = user_id);

create policy "user_badges: pas d'écriture directe côté client"
  on public.user_badges for insert
  with check (false);

-- Débloque un badge une seule fois (idempotent), à appeler depuis les
-- fonctions serveur (update_streak, etc.), jamais directement du client.
create or replace function public.unlock_badge(p_user_id uuid, p_code text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.user_badges (user_id, badge_code)
  values (p_user_id, p_code)
  on conflict (user_id, badge_code) do nothing;
end;
$$;

-- Étend update_streak() pour débloquer les badges de série au passage.
create or replace function public.update_streak(p_user_id uuid)
returns table (jours_consecutifs int, reparation_utilisee boolean)
language plpgsql
security definer set search_path = public
as $$
declare
  v_derniere date;
  v_jours int;
  v_reparations int;
  v_reparation_utilisee boolean := false;
begin
  select derniere_activite, jours_consecutifs, reparations_disponibles
    into v_derniere, v_jours, v_reparations
    from public.streaks where user_id = p_user_id
    for update;

  if v_derniere is null then
    v_jours := 1;
  elsif v_derniere = current_date then
    null;
  elsif v_derniere = current_date - 1 then
    v_jours := v_jours + 1;
  elsif v_derniere < current_date - 1 and v_reparations > 0 then
    v_reparations := v_reparations - 1;
    v_jours := v_jours + 1;
    v_reparation_utilisee := true;
  else
    v_jours := 1;
  end if;

  update public.streaks
    set jours_consecutifs = v_jours,
        reparations_disponibles = v_reparations,
        derniere_activite = current_date
    where user_id = p_user_id;

  if v_reparation_utilisee then
    perform public.unlock_badge(p_user_id, 'reparation_utilisee');
  end if;
  if v_jours >= 7 then
    perform public.unlock_badge(p_user_id, 'streak_7');
  end if;
  if v_jours >= 30 then
    perform public.unlock_badge(p_user_id, 'streak_30');
  end if;

  return query select v_jours, v_reparation_utilisee;
end;
$$;

grant execute on function public.unlock_badge(uuid, text) to authenticated;
grant execute on function public.update_streak(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- plan_from_braindump : décrit toute ta journée en une phrase, l'IA
-- crée directement les tâches (titre + moment de journée + estimation).
-- Même technique que break_down_task (pg_net + Claude + Vault).
-- ---------------------------------------------------------------------------
create or replace function public.plan_from_braindump(p_user_id uuid, p_texte text)
returns jsonb
language plpgsql
security definer
set search_path = public, net, vault, extensions
as $$
declare
  v_api_key text;
  v_system_prompt text;
  v_request_id bigint;
  v_response net._http_response;
  v_body jsonb;
  v_text text;
  v_taches jsonb;
  v_tache jsonb;
  v_attempts int := 0;
  v_created_count int := 0;
begin
  if auth.uid() is distinct from p_user_id then
    raise exception 'Non autorisé';
  end if;

  select decrypted_secret into v_api_key
    from vault.decrypted_secrets where name = 'anthropic_api_key';
  if v_api_key is null then
    raise exception 'Clé Anthropic non configurée';
  end if;

  v_system_prompt := 'Tu aides une personne adulte avec un TDAH à transformer une description libre et en vrac de sa journée en une liste de tâches structurées. '
    || 'Pour chaque tâche identifiée, déduis un moment de journée parmi : n_importe_quand, matin, jour, soir. Estime une durée réaliste en minutes. '
    || 'Ne jamais culpabiliser, reste concis. Réponds UNIQUEMENT en JSON : {"taches": [{"titre": "...", "moment_journee": "matin", "estimation_minutes": 20}, ...]}';

  select net.http_post(
    url := 'https://api.anthropic.com/v1/messages',
    headers := jsonb_build_object(
      'content-type', 'application/json',
      'x-api-key', v_api_key,
      'anthropic-version', '2023-06-01'
    ),
    body := jsonb_build_object(
      'model', 'claude-sonnet-4-5',
      'max_tokens', 600,
      'system', v_system_prompt,
      'messages', jsonb_build_array(jsonb_build_object('role', 'user', 'content', p_texte))
    ),
    timeout_milliseconds := 15000
  ) into v_request_id;

  loop
    select * into v_response from net._http_response where id = v_request_id;
    exit when v_response.id is not null or v_attempts > 50;
    perform pg_sleep(0.2);
    v_attempts := v_attempts + 1;
  end loop;

  if v_response.id is null or v_response.status_code is distinct from 200 then
    raise exception 'Erreur lors de la génération du planning';
  end if;

  v_body := v_response.body::jsonb;
  v_text := v_body -> 'content' -> 0 ->> 'text';
  v_taches := (v_text::jsonb) -> 'taches';

  for v_tache in select * from jsonb_array_elements(v_taches)
  loop
    insert into public.tasks (user_id, titre, moment_journee, estimation_minutes, date_prevue)
    values (
      p_user_id,
      v_tache ->> 'titre',
      coalesce(v_tache ->> 'moment_journee', 'n_importe_quand'),
      (v_tache ->> 'estimation_minutes')::int,
      current_date
    );
    v_created_count := v_created_count + 1;
  end loop;

  if v_created_count > 0 then
    perform public.unlock_badge(p_user_id, 'braindump_premier');
  end if;

  return jsonb_build_object('taches_creees', v_created_count);
end;
$$;

grant execute on function public.plan_from_braindump(uuid, text) to authenticated;
