-- Suite à la recherche approfondie TDAH (science + témoignages) : trois
-- ajouts qui demandent un changement de schéma.
--
-- 1. Plans "si...alors..." (implementation intentions) sur une tâche —
--    preuve scientifique solide (Gawrilow & Gollwitzer et suivants) : ça
--    transfère le contrôle de l'action du cortex préfrontal (déficitaire en
--    TDAH) vers un déclenchement quasi-automatique par un signal
--    environnemental, plutôt que de compter sur la volonté seule.
--
-- 2. Coût en énergie par tâche ("batterie mentale") — les tâches ne coûtent
--    pas toutes la même chose indépendamment de leur durée ; un appel
--    administratif de 5 min peut coûter bien plus qu'une heure de rangement.
--
-- 3. Générateur de réponses aux messages fantômes — même schéma que
--    interpret_schedule_command (0013) : l'IA génère un brouillon de réponse
--    à un message resté sans réponse trop longtemps par évitement/anxiété,
--    l'utilisateur reste libre de l'envoyer, le modifier ou l'ignorer.

alter table public.tasks add column if not exists si_alors text;
alter table public.tasks add column if not exists cout_energie text
  check (cout_energie in ('faible', 'moyen', 'eleve'));

create or replace function public.generate_ghost_reply(p_user_id uuid, p_contexte text)
returns text
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
begin
  if auth.uid() is distinct from p_user_id then
    raise exception 'Non autorisé';
  end if;

  select decrypted_secret into v_api_key
    from vault.decrypted_secrets where name = 'anthropic_api_key';
  if v_api_key is null then
    raise exception 'Clé Anthropic non configurée';
  end if;

  v_system_prompt := 'Tu aides un adulte TDAH à répondre à un message auquel il/elle n''a pas répondu depuis longtemps par évitement ou anxiété (pas par désintérêt). '
    || 'On te donne le contexte du message reçu et de la situation. Écris un brouillon de réponse court (2-4 phrases), chaleureux, honnête sur le délai sans se justifier excessivement ni s''excuser de façon exagérée — une seule mention brève du délai suffit ("désolé pour le silence", "j''ai mis du temps à répondre"), jamais un roman explicatif. '
    || 'Ton naturel, pas robotique, adapté au registre du message d''origine si on peut le déduire. Réponds UNIQUEMENT avec le texte du brouillon, sans guillemets ni préambule.';

  select net.http_post(
    url := 'https://api.anthropic.com/v1/messages',
    headers := jsonb_build_object(
      'content-type', 'application/json',
      'x-api-key', v_api_key,
      'anthropic-version', '2023-06-01'
    ),
    body := jsonb_build_object(
      'model', 'claude-sonnet-4-5',
      'max_tokens', 400,
      'system', v_system_prompt,
      'messages', jsonb_build_array(
        jsonb_build_object('role', 'user', 'content', p_contexte)
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
    raise exception 'Erreur lors de la génération de la réponse';
  end if;

  v_body := v_response.body::jsonb;
  return v_body -> 'content' -> 0 ->> 'text';
end;
$$;

grant execute on function public.generate_ghost_reply(uuid, text) to authenticated;
