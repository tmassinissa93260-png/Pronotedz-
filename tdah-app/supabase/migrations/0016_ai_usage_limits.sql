-- Réajuste la stratégie gratuit/payant pour mieux coller au modèle réel de
-- Tiimo (le concurrent direct le plus établi) : leur IA (générateur de
-- sous-tâches, Co-Planner) reste accessible en gratuit mais LIMITÉE, jamais
-- totalement bloquée — le blocage complet d'une fonctionnalité qu'on a déjà
-- goûtée est justement le piège documenté qui pousse aux désinstalls/1
-- étoile. Le Pro de Tiimo réserve plutôt : sync calendrier, personnalisation,
-- IA illimitée — pas les mécaniques de base du planificateur (routines,
-- liste "à faire" type backlog), qu'on remet donc en gratuit ici aussi.

create table public.ai_usage (
  user_id uuid not null references auth.users (id) on delete cascade,
  mois text not null, -- 'AAAA-MM', mois calendaire courant
  compteur int not null default 0,
  primary key (user_id, mois)
);

alter table public.ai_usage enable row level security;

create policy "ai_usage: lecture de son propre compteur"
  on public.ai_usage for select
  using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Incrémente le compteur du mois courant et retourne la nouvelle valeur —
-- appelée côté client juste après un appel IA réussi (Vide-tête, Assistant,
-- analyse de patterns). Le blocage réel se fait côté client en comparant à
-- la limite gratuite (même limite documentée que le reste du gating dans ce
-- projet : pas encore de vérification serveur dans les fonctions IA
-- elles-mêmes, voir le README).
-- ---------------------------------------------------------------------------
create or replace function public.record_ai_usage(p_user_id uuid)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
  v_mois text := to_char(now(), 'YYYY-MM');
  v_compteur int;
begin
  if auth.uid() is distinct from p_user_id then
    raise exception 'Non autorisé';
  end if;

  insert into public.ai_usage (user_id, mois, compteur)
  values (p_user_id, v_mois, 1)
  on conflict (user_id, mois) do update set compteur = public.ai_usage.compteur + 1
  returning compteur into v_compteur;

  return v_compteur;
end;
$$;

grant execute on function public.record_ai_usage(uuid) to authenticated;

create or replace function public.get_ai_usage(p_user_id uuid)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
  v_mois text := to_char(now(), 'YYYY-MM');
  v_compteur int;
begin
  if auth.uid() is distinct from p_user_id then
    raise exception 'Non autorisé';
  end if;

  select compteur into v_compteur from public.ai_usage where user_id = p_user_id and mois = v_mois;
  return coalesce(v_compteur, 0);
end;
$$;

grant execute on function public.get_ai_usage(uuid) to authenticated;
