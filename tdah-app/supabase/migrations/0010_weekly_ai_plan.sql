-- Plan de semaine complet par IA : extension du Vide-tête (plan_from_braindump,
-- 0005) qui ne planifiait qu'un seul jour. Même technique (pg_net + Claude +
-- Vault), mais l'IA répartit maintenant les tâches sur les 7 jours de la
-- semaine plutôt que de tout entasser sur aujourd'hui.

create or replace function public.plan_week_from_braindump(p_user_id uuid, p_texte text)
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
  v_jour_offset int;
begin
  if auth.uid() is distinct from p_user_id then
    raise exception 'Non autorisé';
  end if;

  select decrypted_secret into v_api_key
    from vault.decrypted_secrets where name = 'anthropic_api_key';
  if v_api_key is null then
    raise exception 'Clé Anthropic non configurée';
  end if;

  v_system_prompt := 'Tu aides une personne adulte avec un TDAH à transformer une description libre de sa semaine (obligations, tâches, envies) en un planning réparti sur 7 jours. '
    || 'Pour chaque tâche identifiée : déduis un jour_offset entre 0 (aujourd''hui) et 6 (dans une semaine) selon le contexte donné (si aucune indication de jour, répartis intelligemment pour ne pas tout entasser sur un seul jour). '
    || 'Déduis aussi un moment de journée parmi : n_importe_quand, matin, jour, soir. Estime une durée réaliste en minutes. '
    || 'Ne jamais culpabiliser, reste concis, ne sur-planifie pas une seule journée. Réponds UNIQUEMENT en JSON : {"taches": [{"titre": "...", "jour_offset": 0, "moment_journee": "matin", "estimation_minutes": 20}, ...]}';

  select net.http_post(
    url := 'https://api.anthropic.com/v1/messages',
    headers := jsonb_build_object(
      'content-type', 'application/json',
      'x-api-key', v_api_key,
      'anthropic-version', '2023-06-01'
    ),
    body := jsonb_build_object(
      'model', 'claude-sonnet-4-5',
      'max_tokens', 1500,
      'system', v_system_prompt,
      'messages', jsonb_build_array(jsonb_build_object('role', 'user', 'content', p_texte))
    ),
    timeout_milliseconds := 20000
  ) into v_request_id;

  loop
    select * into v_response from net._http_response where id = v_request_id;
    exit when v_response.id is not null or v_attempts > 80;
    perform pg_sleep(0.2);
    v_attempts := v_attempts + 1;
  end loop;

  if v_response.id is null or v_response.status_code is distinct from 200 then
    raise exception 'Erreur lors de la génération du planning de semaine';
  end if;

  v_body := v_response.body::jsonb;
  v_text := v_body -> 'content' -> 0 ->> 'text';
  v_taches := (v_text::jsonb) -> 'taches';

  for v_tache in select * from jsonb_array_elements(v_taches)
  loop
    v_jour_offset := greatest(0, least(6, coalesce((v_tache ->> 'jour_offset')::int, 0)));
    insert into public.tasks (user_id, titre, moment_journee, estimation_minutes, date_prevue)
    values (
      p_user_id,
      v_tache ->> 'titre',
      coalesce(v_tache ->> 'moment_journee', 'n_importe_quand'),
      (v_tache ->> 'estimation_minutes')::int,
      current_date + v_jour_offset
    );
    v_created_count := v_created_count + 1;
  end loop;

  return jsonb_build_object('taches_creees', v_created_count);
end;
$$;

grant execute on function public.plan_week_from_braindump(uuid, text) to authenticated;
