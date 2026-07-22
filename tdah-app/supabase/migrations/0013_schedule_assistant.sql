-- Assistant conversationnel de planning (façon le chat IA de Tiimo qui exécute
-- des commandes : "I'm late, move all my tasks by 10min", "Everything feels
-- urgent, I don't know where to begin"). Plutôt qu'un chat libre qui écrit
-- directement en base (risqué, imprévisible), l'IA classe le message dans un
-- jeu d'actions fixe et déterministe ; c'est le client qui exécute la mutation
-- réelle, en réutilisant la logique déjà existante (décalage, report, priorité).

create or replace function public.interpret_schedule_command(p_user_id uuid, p_texte text, p_taches jsonb)
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
begin
  if auth.uid() is distinct from p_user_id then
    raise exception 'Non autorisé';
  end if;

  select decrypted_secret into v_api_key
    from vault.decrypted_secrets where name = 'anthropic_api_key';
  if v_api_key is null then
    raise exception 'Clé Anthropic non configurée';
  end if;

  v_system_prompt := 'Tu es l''assistant de planning d''une appli pour adultes TDAH. On te donne un message libre de l''utilisateur et la liste de ses tâches du jour (id, titre, heure_debut, niveau_priorite, niveau_dread, statut). '
    || 'Tu dois classer ce message dans UNE seule action parmi : "decaler_tout" (il est en retard, veut décaler toutes ses tâches restantes d''un nombre de minutes — déduis les minutes, 10 par défaut si non précisé), '
    || '"reporter_tache" (il veut reporter une tâche précise à demain — retrouve son id dans la liste en comparant avec son titre), '
    || '"prioriser" (il veut marquer une tâche précise comme prioritaire — retrouve son id, niveau_priorite = haute/moyenne/basse), '
    || '"repondre" (tout le reste : question, message vague type "tout me semble urgent, je ne sais pas par où commencer", encouragement demandé...). '
    || 'Pour "repondre", si la liste de tâches permet de repérer une tâche qui se distingue (priorité haute, ou angoisse élevée, ou l''heure la plus proche), suggère-la nommément dans le message plutôt que de rester vague. '
    || 'Ton toujours bienveillant, jamais culpabilisant, jamais péremptoire, 1-2 phrases max, en français. '
    || 'Réponds UNIQUEMENT en JSON strict : {"action": "decaler_tout"|"reporter_tache"|"prioriser"|"repondre", "minutes": <entier ou null>, "tache_id": "<uuid ou null>", "niveau_priorite": "haute"|"moyenne"|"basse"|null, "message": "<réponse courte>"}';

  select net.http_post(
    url := 'https://api.anthropic.com/v1/messages',
    headers := jsonb_build_object(
      'content-type', 'application/json',
      'x-api-key', v_api_key,
      'anthropic-version', '2023-06-01'
    ),
    body := jsonb_build_object(
      'model', 'claude-sonnet-4-5',
      'max_tokens', 500,
      'system', v_system_prompt,
      'messages', jsonb_build_array(
        jsonb_build_object(
          'role', 'user',
          'content', 'Message : ' || p_texte || E'\n\nTâches du jour (JSON) : ' || p_taches::text
        )
      )
    ),
    timeout_milliseconds := 20000
  ) into v_request_id;

  declare
    v_attempts int := 0;
  begin
    loop
      select * into v_response from net._http_response where id = v_request_id;
      exit when v_response.id is not null or v_attempts > 80;
      perform pg_sleep(0.2);
      v_attempts := v_attempts + 1;
    end loop;
  end;

  if v_response.id is null or v_response.status_code is distinct from 200 then
    raise exception 'Erreur lors de l''interprétation de la commande';
  end if;

  v_body := v_response.body::jsonb;
  v_text := v_body -> 'content' -> 0 ->> 'text';

  return v_text::jsonb;
end;
$$;

grant execute on function public.interpret_schedule_command(uuid, text, jsonb) to authenticated;
