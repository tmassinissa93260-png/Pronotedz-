-- Niveau d'angoisse par tâche (fusion Goblin Tools "spiciness" + Eat the
-- Frog d'Amazing Marvin) et rituel de fin de journée façon Sunsama.

alter table public.tasks
  add column niveau_dread int check (niveau_dread between 1 and 5);

create table public.daily_reviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  date_jour date not null default current_date,
  accompli text,
  bascule_demain text,
  ressenti text,
  created_at timestamptz not null default now(),
  unique (user_id, date_jour)
);

alter table public.daily_reviews enable row level security;

create policy "daily_reviews: propriétaire uniquement"
  on public.daily_reviews for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- break_down_task tient maintenant compte du niveau d'angoisse : plus il est
-- élevé, plus les étapes doivent être petites (le curseur de granularité
-- reste un réglage manuel indépendant, le dread vient en plus).
create or replace function public.break_down_task(
  p_titre text,
  p_preference_ton text default 'doux',
  p_granularite int default 2,
  p_niveau_dread int default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, net, vault, extensions
as $$
declare
  v_api_key text;
  v_ton_instruction text;
  v_gran_instruction text;
  v_dread_instruction text;
  v_system_prompt text;
  v_request_id bigint;
  v_response net._http_response;
  v_body jsonb;
  v_text text;
  v_attempts int := 0;
begin
  if auth.uid() is null then
    raise exception 'Non authentifié';
  end if;

  select decrypted_secret into v_api_key
    from vault.decrypted_secrets where name = 'anthropic_api_key';
  if v_api_key is null then
    raise exception 'Clé Anthropic non configurée (vault)';
  end if;

  v_ton_instruction := case p_preference_ton
    when 'direct' then 'Ton direct et concis, sans fioritures.'
    when 'humoristique' then 'Ton léger, avec une pointe d''humour, sans être lourd.'
    else 'Ton bienveillant, jamais culpabilisant.'
  end;

  v_gran_instruction := case p_granularite
    when 1 then '2 à 3 sous-étapes larges seulement — l''utilisateur a de l''énergie, ne le noie pas de détails.'
    when 3 then '6 à 10 sous-étapes minuscules, chacune démarrable en moins de 30 secondes de réflexion.'
    else '3 à 5 sous-étapes, niveau standard.'
  end;

  v_dread_instruction := case
    when p_niveau_dread is null then ''
    when p_niveau_dread >= 4 then ' Cette tâche est décrite comme très angoissante pour l''utilisateur (niveau 4-5/5) : la toute première sous-étape doit être ridiculement petite et non-menaçante (ex: "ouvrir le document", "sortir le dossier"), pour casser l''évitement.'
    when p_niveau_dread <= 2 then ' Cette tâche est peu angoissante pour l''utilisateur, tu peux rester efficace sans sur-découper.'
    else ''
  end;

  v_system_prompt := 'Tu aides une personne adulte avec un TDAH à décomposer une tâche floue en sous-étapes très concrètes et actionnables (chacune une action physique précise, pas un objectif abstrait). '
    || 'Granularité demandée : ' || v_gran_instruction || v_dread_instruction || ' '
    || v_ton_instruction
    || ' Ne jamais culpabiliser, ne jamais dire "il suffit de". Réponds UNIQUEMENT avec un JSON valide : {"sous_taches": ["...", "..."]}';

  select net.http_post(
    url := 'https://api.anthropic.com/v1/messages',
    headers := jsonb_build_object(
      'content-type', 'application/json',
      'x-api-key', v_api_key,
      'anthropic-version', '2023-06-01'
    ),
    body := jsonb_build_object(
      'model', 'claude-sonnet-4-5',
      'max_tokens', 512,
      'system', v_system_prompt,
      'messages', jsonb_build_array(jsonb_build_object('role', 'user', 'content', 'Tâche à décomposer : "' || p_titre || '"'))
    ),
    timeout_milliseconds := 15000
  ) into v_request_id;

  loop
    select * into v_response from net._http_response where id = v_request_id;
    exit when v_response.id is not null or v_attempts > 50;
    perform pg_sleep(0.2);
    v_attempts := v_attempts + 1;
  end loop;

  if v_response.id is null then
    raise exception 'Timeout en attendant la réponse de Claude';
  end if;

  if v_response.status_code is distinct from 200 then
    raise exception 'Erreur API Claude (% ): %', v_response.status_code, v_response.body;
  end if;

  v_body := v_response.body::jsonb;
  v_text := v_body -> 'content' -> 0 ->> 'text';

  return v_text::jsonb;
end;
$$;

grant execute on function public.break_down_task(text, text, int, int) to authenticated;
