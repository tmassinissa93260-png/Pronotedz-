# Architecture SaaS v2 — brief du 2026-08-05

**Contexte** : développeur solo, stack Lovable + Supabase + n8n, sans background
ingénierie classique. Budget infra < 200 €/mois. Cible : 50 utilisateurs payants
à 6 mois, architecture qui tienne à 5 000 sans réécriture complète.

**Produit** : analyse d'une vidéo TikTok fournie par l'utilisateur, extraction de sa
structure de performance, génération d'une nouvelle vidéo appliquant cette structure
à un sujet différent. Validation humaine à chaque étape clé.

## Sections

**Automatisation** : Claude (IA) + n8n (orchestration), confirmé par le porteur du projet.

| # | Section | Statut |
|---|---|---|
| 1 | [Faisabilité d'abord](./01-faisabilite.md) | ✅ |
| 2 | [Architecture globale](./02-architecture-globale.md) | ✅ |
| 3 | [Ce qui va dans n8n — et ce qui n'y va pas](./03-n8n.md) | ✅ |
| 4 | Modèle de données Supabase | ⏳ |
| 5 | Pipeline de génération et validations humaines | ⏳ |
| 6 | Rendu vidéo — le trou de la stack | ⏳ |
| 7 | Budget < 200 €/mois et coût unitaire | ⏳ |
| 8 | Chemin 50 → 5 000 utilisateurs | ⏳ |
| 9 | Risques | ⏳ |
| 10 | Roadmap | ⏳ |

*(Le brief d'origine était tronqué à `courbe aud…` ; la liste de sections 2 à 10
ci-dessus a été proposée puis validée.)*

## Les 3 décisions structurantes déjà prises

1. **Il manque une brique à la stack** : ni Lovable, ni Supabase, ni n8n ne savent
   analyser ou monter une vidéo. Un **service média** custom (3 endpoints) est
   nécessaire — c'est le seul composant hors low-code du système.
2. **n8n auto-hébergé sur le même VPS que le service média**, pas n8n Cloud : le
   comptage d'exécutions du forfait Starter est dépassé dès ~50 utilisateurs.
3. **Aucune attente humaine dans n8n.** Chaque validation termine un workflow ;
   l'approbation en déclenche un neuf via Database Webhook. C'est ce qui découpe le
   pipeline en 4 workflows au lieu d'un.

## Rapport avec les autres dossiers du dépôt

- `docs/` (racine) — version « agent personnel mono-utilisateur ». Périmètre différent,
  conservée telle quelle.
- `docs/saas-plus-tard/` — première architecture SaaS (multi-tenant lourd, PostgreSQL,
  FastAPI, workers). Utile comme référence sur la reprise, le cache et le registre de
  prompts, mais surdimensionnée pour ce brief-ci et incompatible avec la stack
  Lovable/Supabase/n8n imposée.
