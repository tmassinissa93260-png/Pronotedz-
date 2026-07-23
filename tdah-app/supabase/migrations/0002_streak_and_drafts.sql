-- Logique de streak réelle (avec réparation, jamais de rupture punitive
-- brutale) + table pour le brouillon différé (RSD).

-- ---------------------------------------------------------------------------
-- update_streak() : à appeler (via RPC) à chaque engagement significatif
-- (tâche finie, sous-tâche cochée, check-in répondu, session focus terminée).
-- ---------------------------------------------------------------------------
create function public.update_streak(p_user_id uuid)
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
    -- déjà comptabilisé aujourd'hui, rien à changer
    null;
  elsif v_derniere = current_date - 1 then
    v_jours := v_jours + 1;
  elsif v_derniere < current_date - 1 and v_reparations > 0 then
    -- un ou plusieurs jours manqués, mais on répare au lieu de tout casser
    v_reparations := v_reparations - 1;
    v_jours := v_jours + 1;
    v_reparation_utilisee := true;
  else
    -- pas de réparation dispo : on repart à 1, jamais en dessous
    v_jours := 1;
  end if;

  update public.streaks
    set jours_consecutifs = v_jours,
        reparations_disponibles = v_reparations,
        derniere_activite = current_date
    where user_id = p_user_id;

  return query select v_jours, v_reparation_utilisee;
end;
$$;

grant execute on function public.update_streak(uuid) to authenticated;

-- Recharge une réparation par mois entamé (à appeler depuis un cron Supabase,
-- pas critique pour le MVP mais évite que les réparations s'épuisent pour de bon).
create function public.recharger_reparations()
returns void
language sql
security definer set search_path = public
as $$
  update public.streaks set reparations_disponibles = least(reparations_disponibles + 1, 2);
$$;

-- ---------------------------------------------------------------------------
-- delayed_drafts : brouillon différé pour les messages envoyés en détresse
-- (dysphorie sensible au rejet). L'app ne touche à aucune vraie messagerie —
-- c'est un espace de "temporisation" que l'utilisateur ouvre lui-même avant
-- d'envoyer un message ailleurs (SMS, email, etc.).
-- ---------------------------------------------------------------------------
create table public.delayed_drafts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  contenu text not null,
  envoyer_apres timestamptz not null,
  statut text not null check (statut in ('en_attente', 'valide', 'annule')) default 'en_attente',
  created_at timestamptz not null default now()
);

alter table public.delayed_drafts enable row level security;

create policy "delayed_drafts: propriétaire uniquement"
  on public.delayed_drafts for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
