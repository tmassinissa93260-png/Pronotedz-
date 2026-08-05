# Architecture SaaS v2 — brief du 2026-08-05

**Contexte** : développeur solo, stack Lovable + Supabase + n8n, sans background
ingénierie classique. Budget infra < 200 €/mois. Cible : 50 utilisateurs payants
à 6 mois, architecture qui tienne à 5 000 sans réécriture complète.

**Produit** : analyse d'une vidéo TikTok fournie par l'utilisateur, extraction de sa
structure de performance, génération d'une nouvelle vidéo appliquant cette structure
à un sujet différent. Validation humaine à chaque étape clé.

## Sections

| # | Section | Statut |
|---|---|---|
| 1 | [Faisabilité d'abord](./01-faisabilite.md) | ✅ livrée |
| 2+ | — | ⏳ **liste de sections manquante** — le brief était tronqué à `courbe aud…` |

## Rapport avec les autres dossiers du dépôt

- `docs/` (racine) — version « agent personnel mono-utilisateur ». Périmètre différent,
  conservée telle quelle.
- `docs/saas-plus-tard/` — première architecture SaaS (multi-tenant lourd, PostgreSQL,
  FastAPI, workers). Utile comme référence sur la reprise, le cache et le registre de
  prompts, mais surdimensionnée pour ce brief-ci et incompatible avec la stack
  Lovable/Supabase/n8n imposée.
