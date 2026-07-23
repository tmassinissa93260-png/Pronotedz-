-- Essai premium gratuit de 7 jours à l'inscription, sans carte bancaire à
-- fournir. Pression de conversion "invisible" : l'app est généreuse par
-- défaut dès le premier jour, la limite ne se sent qu'à la fin de l'essai
-- (aversion à la perte plutôt qu'un mur de vente). Se combine avec le
-- statut Stripe existant : premium = abonnement actif OU essai en cours.

alter table public.profiles add column if not exists essai_premium_fin timestamptz;

update public.profiles
  set essai_premium_fin = created_at + interval '7 days'
  where essai_premium_fin is null;

alter table public.profiles
  alter column essai_premium_fin set default (now() + interval '7 days'),
  alter column essai_premium_fin set not null;
