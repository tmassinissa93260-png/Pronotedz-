-- Mémoire longue durée : analyse les tâches/check-ins/sessions accumulés
-- pour détecter de vrais patterns personnels ("tu craques le jeudi
-- après-midi depuis 3 mois"), pas juste stocker des chiffres bruts.
-- Nécessite un minimum d'historique pour être pertinent (voir garde-fou
-- v_jours_historique ci-dessous) — inutile de l'appeler avant plusieurs
-- semaines d'usage réel, mais la fonction est prête dès maintenant.

create or replace function public.generate_pattern_insight(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, net, vault, extensions
as $$
declare
  v_api_key text;
  v_jours_historique int;
  v_taches_resume text;
  v_checkins_resume text;
  v_sessions_resume text;
  v_system_prompt text;
  v_request_id bigint;
  v_response net._http_response;
  v_body jsonb;
  v_text text;
  v_result jsonb;
  v_attempts int := 0;
begin
  if auth.uid() is distinct from p_user_id then
    raise exception 'Non autorisé';
  end if;

  -- Garde-fou : pas assez d'historique pour qu'une analyse ait du sens.
  select extract(day from now() - min(created_at))::int into v_jours_historique
    from public.tasks where user_id = p_user_id;

  if v_jours_historique is null or v_jours_historique < 21 then
    return jsonb_build_object(
      'pret', false,
      'message', 'Pas encore assez d''historique (encore ' || greatest(0, 21 - coalesce(v_jours_historique, 0)) || ' jours environ) pour un insight fiable.'
    );
  end if;

  select decrypted_secret into v_api_key
    from vault.decrypted_secrets where name = 'anthropic_api_key';
  if v_api_key is null then
    raise exception 'Clé Anthropic non configurée';
  end if;

  -- Résumés compacts (pas les lignes brutes) pour limiter le volume envoyé
  -- à l'IA et donc le coût — un pré-agrégat SQL plutôt qu'un dump complet.
  select string_agg(
      to_char(date_prevue, 'Dy') || ': ' || count(*) filter (where statut = 'fait') || '/' || count(*) || ' faites, temps réel moyen '
      || coalesce(round(avg(temps_reel_minutes))::text, 'n/a') || ' min vs estimé ' || coalesce(round(avg(estimation_minutes))::text, 'n/a') || ' min',
      chr(10)
    )
    into v_taches_resume
  from (
    select date_prevue, statut, temps_reel_minutes, estimation_minutes
    from public.tasks
    where user_id = p_user_id and date_prevue > current_date - 60
  ) t
  group by to_char(date_prevue, 'Dy'), extract(dow from date_prevue)
  order by extract(dow from date_prevue);

  select string_agg(type || ' → ' || reponse || ' (' || count(*) || 'x)', ', ')
    into v_checkins_resume
  from public.checkins
  where user_id = p_user_id and created_at > now() - interval '60 days'
  group by type, reponse;

  select 'moyenne ' || round(avg(duree_minutes)) || ' min, ' || count(*) || ' sessions sur 60 jours, répartition ' ||
    string_agg(distinct type, '/')
    into v_sessions_resume
  from public.sessions
  where user_id = p_user_id and started_at > now() - interval '60 days' and duree_minutes is not null;

  v_system_prompt := 'Tu analyses les données d''usage d''une app pour adulte TDAH sur les 60 derniers jours et tu identifies UN SEUL pattern concret et actionnable (pas une observation vague). '
    || 'Sois factuel, base-toi uniquement sur les chiffres donnés, ne culpabilise jamais. '
    || 'Réponds UNIQUEMENT en JSON : {"pattern": "phrase courte et concrète (max 200 caractères)", "confiance": 0.0 à 1.0, "suggestion": "une action concrète à essayer"}';

  select net.http_post(
    url := 'https://api.anthropic.com/v1/messages',
    headers := jsonb_build_object(
      'content-type', 'application/json',
      'x-api-key', v_api_key,
      'anthropic-version', '2023-06-01'
    ),
    body := jsonb_build_object(
      'model', 'claude-sonnet-4-5',
      'max_tokens', 300,
      'system', v_system_prompt,
      'messages', jsonb_build_array(jsonb_build_object(
        'role', 'user',
        'content', 'Tâches par jour de la semaine (60 derniers jours) :' || chr(10) || coalesce(v_taches_resume, 'aucune donnée')
          || chr(10) || chr(10) || 'Check-ins d''interoception : ' || coalesce(v_checkins_resume, 'aucun')
          || chr(10) || chr(10) || 'Sessions focus : ' || coalesce(v_sessions_resume, 'aucune')
      ))
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
    raise exception 'Erreur lors de la génération de l''insight';
  end if;

  v_body := v_response.body::jsonb;
  v_text := v_body -> 'content' -> 0 ->> 'text';
  v_result := v_text::jsonb;

  insert into public.pattern_memory (user_id, pattern_detecte, confiance)
  values (p_user_id, v_result ->> 'pattern', (v_result ->> 'confiance')::numeric);

  return jsonb_build_object('pret', true) || v_result;
end;
$$;

grant execute on function public.generate_pattern_insight(uuid) to authenticated;
