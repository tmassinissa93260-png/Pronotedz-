# 📦 Archive — architecture SaaS

**Ce dossier ne sert pas au projet actuel.**

Il contient la première version de l'architecture, conçue pour un **SaaS multi-clients**
(milliers d'utilisateurs, facturation, agences, montée en charge).

Le projet a été recentré sur un **agent personnel** — un outil pour une seule personne,
qui tourne en local. Voir la [documentation actuelle](../01-comment-ca-marche.md).

## À quoi ça peut servir plus tard

Si un jour l'outil perso devient un produit vendu à d'autres, tout est déjà pensé ici :

- Multi-clients avec isolation des données (PostgreSQL + RLS)
- Facturation Stripe, crédits, formules d'abonnement
- Files d'attente, workers, montée en charge horizontale
- Observabilité complète (Grafana, Prometheus, Langfuse)
- Les 17 workflows n8n
- Le registre de risques juridiques (droits d'auteur, CGU des plateformes)
- Les 5 décisions d'architecture argumentées (dossier `adr/`)

## Ce qui a survécu dans la version perso

Les mécanismes qui servent autant à 1 personne qu'à 1000 :
la reprise après plantage, le cache par empreinte de contenu, le versionnement des
prompts, le registre de modèles IA, le contrat commun des agents, et le schéma de la
recette virale.
