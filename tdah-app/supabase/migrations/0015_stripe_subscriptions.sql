-- Infrastructure d'abonnement (Stripe) — construite maintenant à la demande
-- explicite, mais AUCUNE fonctionnalité n'est verrouillée derrière pour
-- l'instant : la répartition gratuit/payant sera décidée plus tard, une
-- fois que toutes les fonctionnalités prévues seront terminées.
--
-- Choix technique : Stripe Checkout (page hébergée par Stripe, ouverte dans
-- le navigateur du téléphone via expo-web-browser) plutôt que le SDK natif
-- @stripe/stripe-react-native — ce dernier casserait Expo Go (module natif
-- non lié). Aucun webhook non plus (nécessiterait un point d'entrée HTTP
-- public, hors du pattern pg_net sortant utilisé partout ailleurs dans ce
-- projet) : la confirmation se fait par un appel sortant vers l'API Stripe
-- juste après le retour dans l'app, et un rafraîchissement à l'ouverture de
-- l'écran Profil pour rester à jour sans webhook. pg_net envoie du JSON
-- (pas de form-urlencoded possible), donc on utilise le support JSON de
-- l'API Stripe — officiellement recommandé pour les structures imbriquées
-- comme line_items.

create table public.subscriptions (
  user_id uuid primary key references auth.users (id) on delete cascade,
  stripe_customer_id text,
  stripe_subscription_id text,
  statut text not null default 'gratuit' check (statut in ('gratuit', 'actif', 'annule', 'expire')),
  plan text check (plan in ('mensuel', 'annuel')),
  periode_fin timestamptz,
  updated_at timestamptz not null default now()
);

alter table public.subscriptions enable row level security;

create policy "subscriptions: lecture de son propre abonnement"
  on public.subscriptions for select
  using (auth.uid() = user_id);

-- Pas d'écriture directe côté client : uniquement via les fonctions
-- SECURITY DEFINER ci-dessous, qui vérifient le paiement auprès de Stripe
-- avant d'écrire quoi que ce soit.

-- ---------------------------------------------------------------------------
-- Crée (ou réutilise) un client Stripe pour l'utilisateur, puis une session
-- Checkout pour le plan choisi. Retourne l'URL à ouvrir dans le navigateur.
--
-- p_redirect_base est fourni par le client (Linking.createURL('checkout-retour'))
-- plutôt que codé en dur ici : le schéma d'URL qui rouvre l'app diffère entre
-- Expo Go (exp://...) et un vrai build EAS (tdahapp://...) — en dur, ça
-- aurait marché en build mais pas pendant les tests sous Expo Go.
-- ---------------------------------------------------------------------------
create or replace function public.create_checkout_session(p_user_id uuid, p_plan text, p_redirect_base text)
returns jsonb
language plpgsql
security definer
set search_path = public, net, vault, extensions
as $$
declare
  v_secret_key text;
  v_price_id text;
  v_customer_id text;
  v_email text;
  v_request_id bigint;
  v_response net._http_response;
  v_body jsonb;
  v_attempts int;
begin
  if auth.uid() is distinct from p_user_id then
    raise exception 'Non autorisé';
  end if;
  if p_plan not in ('mensuel', 'annuel') then
    raise exception 'Plan invalide';
  end if;

  select decrypted_secret into v_secret_key from vault.decrypted_secrets where name = 'stripe_secret_key';
  if v_secret_key is null then
    raise exception 'Clé Stripe non configurée';
  end if;

  select decrypted_secret into v_price_id
    from vault.decrypted_secrets
    where name = case when p_plan = 'mensuel' then 'stripe_price_mensuel' else 'stripe_price_annuel' end;
  if v_price_id is null then
    raise exception 'Prix Stripe non configuré pour ce plan';
  end if;

  select stripe_customer_id into v_customer_id from public.subscriptions where user_id = p_user_id;

  if v_customer_id is null then
    select email into v_email from auth.users where id = p_user_id;

    select net.http_post(
      url := 'https://api.stripe.com/v1/customers',
      headers := jsonb_build_object(
        'content-type', 'application/json',
        'authorization', 'Bearer ' || v_secret_key
      ),
      body := jsonb_build_object('email', coalesce(v_email, '')),
      timeout_milliseconds := 15000
    ) into v_request_id;

    v_attempts := 0;
    loop
      select * into v_response from net._http_response where id = v_request_id;
      exit when v_response.id is not null or v_attempts > 60;
      perform pg_sleep(0.2);
      v_attempts := v_attempts + 1;
    end loop;

    if v_response.id is null or v_response.status_code is distinct from 200 then
      raise exception 'Erreur lors de la création du client Stripe';
    end if;

    v_customer_id := (v_response.body::jsonb) ->> 'id';

    insert into public.subscriptions (user_id, stripe_customer_id, plan)
    values (p_user_id, v_customer_id, p_plan)
    on conflict (user_id) do update set stripe_customer_id = excluded.stripe_customer_id, plan = p_plan, updated_at = now();
  else
    update public.subscriptions set plan = p_plan, updated_at = now() where user_id = p_user_id;
  end if;

  select net.http_post(
    url := 'https://api.stripe.com/v1/checkout/sessions',
    headers := jsonb_build_object(
      'content-type', 'application/json',
      'authorization', 'Bearer ' || v_secret_key
    ),
    body := jsonb_build_object(
      'mode', 'subscription',
      'customer', v_customer_id,
      'client_reference_id', p_user_id::text,
      'line_items', jsonb_build_array(jsonb_build_object('price', v_price_id, 'quantity', 1)),
      'success_url', p_redirect_base || '?session_id={CHECKOUT_SESSION_ID}',
      'cancel_url', p_redirect_base || '?annule=1'
    ),
    timeout_milliseconds := 15000
  ) into v_request_id;

  v_attempts := 0;
  loop
    select * into v_response from net._http_response where id = v_request_id;
    exit when v_response.id is not null or v_attempts > 60;
    perform pg_sleep(0.2);
    v_attempts := v_attempts + 1;
  end loop;

  if v_response.id is null or v_response.status_code is distinct from 200 then
    raise exception 'Erreur lors de la création de la session de paiement';
  end if;

  v_body := v_response.body::jsonb;
  return jsonb_build_object('url', v_body ->> 'url');
end;
$$;

grant execute on function public.create_checkout_session(uuid, text, text) to authenticated;

-- ---------------------------------------------------------------------------
-- Appelée juste après le retour dans l'app depuis Stripe Checkout (via le
-- lien tdahapp://checkout-retour) : vérifie auprès de Stripe que la session
-- a vraiment été payée avant d'activer l'abonnement — jamais sur la seule
-- foi du paramètre d'URL, qui pourrait être falsifié côté client.
-- ---------------------------------------------------------------------------
create or replace function public.confirm_checkout_session(p_user_id uuid, p_session_id text)
returns jsonb
language plpgsql
security definer
set search_path = public, net, vault, extensions
as $$
declare
  v_secret_key text;
  v_request_id bigint;
  v_response net._http_response;
  v_body jsonb;
  v_attempts int := 0;
  v_subscription_id text;
  v_period_end timestamptz;
begin
  if auth.uid() is distinct from p_user_id then
    raise exception 'Non autorisé';
  end if;

  select decrypted_secret into v_secret_key from vault.decrypted_secrets where name = 'stripe_secret_key';
  if v_secret_key is null then
    raise exception 'Clé Stripe non configurée';
  end if;

  select net.http_get(
    url := 'https://api.stripe.com/v1/checkout/sessions/' || p_session_id,
    params := jsonb_build_object('expand[]', 'subscription'),
    headers := jsonb_build_object('authorization', 'Bearer ' || v_secret_key),
    timeout_milliseconds := 15000
  ) into v_request_id;

  loop
    select * into v_response from net._http_response where id = v_request_id;
    exit when v_response.id is not null or v_attempts > 60;
    perform pg_sleep(0.2);
    v_attempts := v_attempts + 1;
  end loop;

  if v_response.id is null or v_response.status_code is distinct from 200 then
    raise exception 'Erreur lors de la vérification du paiement';
  end if;

  v_body := v_response.body::jsonb;

  if v_body ->> 'client_reference_id' is distinct from p_user_id::text then
    raise exception 'Session de paiement invalide';
  end if;

  if v_body ->> 'payment_status' is distinct from 'paid' then
    return jsonb_build_object('statut', 'gratuit');
  end if;

  v_subscription_id := v_body -> 'subscription' ->> 'id';
  v_period_end := to_timestamp((v_body -> 'subscription' ->> 'current_period_end')::bigint);

  update public.subscriptions
    set statut = 'actif',
        stripe_subscription_id = v_subscription_id,
        periode_fin = v_period_end,
        updated_at = now()
    where user_id = p_user_id;

  return jsonb_build_object('statut', 'actif', 'periode_fin', v_period_end);
end;
$$;

grant execute on function public.confirm_checkout_session(uuid, text) to authenticated;

-- ---------------------------------------------------------------------------
-- Rafraîchit le statut réel depuis Stripe (appelée à l'ouverture de l'écran
-- Profil) — remplace le besoin d'un webhook pour capter les
-- renouvellements/annulations, au prix d'un léger différé plutôt que du
-- temps réel.
-- ---------------------------------------------------------------------------
create or replace function public.refresh_subscription_status(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, net, vault, extensions
as $$
declare
  v_secret_key text;
  v_subscription_id text;
  v_request_id bigint;
  v_response net._http_response;
  v_body jsonb;
  v_attempts int := 0;
  v_stripe_status text;
  v_statut text;
begin
  if auth.uid() is distinct from p_user_id then
    raise exception 'Non autorisé';
  end if;

  select stripe_subscription_id into v_subscription_id from public.subscriptions where user_id = p_user_id;
  if v_subscription_id is null then
    return jsonb_build_object('statut', 'gratuit');
  end if;

  select decrypted_secret into v_secret_key from vault.decrypted_secrets where name = 'stripe_secret_key';
  if v_secret_key is null then
    raise exception 'Clé Stripe non configurée';
  end if;

  select net.http_get(
    url := 'https://api.stripe.com/v1/subscriptions/' || v_subscription_id,
    headers := jsonb_build_object('authorization', 'Bearer ' || v_secret_key),
    timeout_milliseconds := 15000
  ) into v_request_id;

  loop
    select * into v_response from net._http_response where id = v_request_id;
    exit when v_response.id is not null or v_attempts > 60;
    perform pg_sleep(0.2);
    v_attempts := v_attempts + 1;
  end loop;

  if v_response.id is null or v_response.status_code is distinct from 200 then
    raise exception 'Erreur lors du rafraîchissement de l''abonnement';
  end if;

  v_body := v_response.body::jsonb;
  v_stripe_status := v_body ->> 'status';
  v_statut := case
    when v_stripe_status in ('active', 'trialing') then 'actif'
    when v_stripe_status in ('canceled', 'unpaid') then 'annule'
    when v_stripe_status = 'past_due' then 'expire'
    else 'gratuit'
  end;

  update public.subscriptions
    set statut = v_statut,
        periode_fin = to_timestamp((v_body ->> 'current_period_end')::bigint),
        updated_at = now()
    where user_id = p_user_id;

  return jsonb_build_object('statut', v_statut);
end;
$$;

grant execute on function public.refresh_subscription_status(uuid) to authenticated;
