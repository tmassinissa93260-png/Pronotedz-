# 13 — Points à améliorer & évolutions possibles

## 1. Faiblesses assumées de cette architecture

Honnêtement listées : ce sont des choix, pas des oublis.

| # | Faiblesse | Pourquoi c'est accepté | Seuil de correction |
|---|---|---|---|
| 1 | **SPOF PostgreSQL** — pas de réplique | budget ; PITR + snapshots limitent la perte à ~15 min | > 200 utilisateurs payants |
| 2 | **Redis sans persistance forte** | les files sont reconstructibles depuis PG | jamais critique par conception |
| 3 | **Pas de Vault** — secrets en variables d'environnement | 0 € vs complexité | équipe > 2 personnes |
| 4 | **Moteur de pipeline maison** | contrôle total sur checkpoints/budget ; Temporal coûte 90 €/mois | > 10 types de pipelines ou besoin de durabilité stricte |
| 5 | **Rendu ffmpeg** — moins expressif que Remotion | licence | revenus > 2 k€/mois |
| 6 | **Déploiement Docker Compose**, pas de Kubernetes | complexité injustifiée à cette échelle | > 5 nœuds |
| 7 | **Pas d'A/B testing de contenu intégré** | demande du volume pour avoir du sens | > 1 000 vidéos publiées |
| 8 | **Mémoire procédurale non automatique** | garde-fou anti-dérive volontaire (P4) | quand les métriques seront statistiquement solides |
| 9 | **Français/anglais seulement** | qualité TTS et prompts | demande marché |
| 10 | **Pas de mode multi-utilisateur collaboratif** (revue en équipe) | complexité | clients agences |

## 2. Améliorations à court terme (post-v1, sans changement d'architecture)

- **Régénération partielle par scène** : « refais seulement la scène 4 ». L'adressage par
  contenu le permet déjà, il ne manque que l'UI et l'endpoint.
- **Bibliothèque d'ADN partagée** entre utilisateurs (templates publics, avec opt-in).
- **Presets de marque** : plusieurs identités par organisation (multi-clients pour agences).
- **Import de b-roll** utilisateur, mêlé aux images IA.
- **Éditeur de sous-titres** dans l'UI, avec re-render incrémental (< 5 s, sans réencodage).
- **Score de viralité prédictif** avant publication, calibré sur `publication_metrics`.
- **Batch generation** : 10 vidéos depuis un même ADN et 10 sujets, en une commande.
- **Webhooks sortants** pour les clients qui veulent brancher leur propre outillage.

## 3. Évolutions v2 — produit

| Évolution | Valeur | Coût / prérequis |
|---|---|---|
| **Génération vidéo** (Kling, Veo, Seedance) au lieu d'images fixes | saut qualitatif majeur | 0,30–1,50 €/vidéo → plan premium uniquement |
| **Avatars parlants** (HeyGen, lip-sync open source) | format très performant | licence + coût GPU |
| **Clonage de voix** de l'utilisateur | personnalisation forte | ⚠️ consentement explicite, risque deepfake |
| **Analyse de compte complet** (50 vidéos → ADN de créateur) | offre agence | coût d'analyse ×50, à tarifer |
| **Recherche de tendances** (sons, formats, hashtags du moment) | timing = viralité | API tierces payantes |
| **Multi-langue + doublage** | ×5 marché adressable | TTS multilingue |
| **Extension navigateur** « analyser cette vidéo » | acquisition | — |
| **API publique** | revenus B2B | rate limiting, docs, SLA |

## 4. Évolutions v3 — plateforme

- **Marketplace de StyleTemplates** avec revenus partagés pour les créateurs d'ADN performants.
- **Fine-tuning / distillation** : un petit modèle spécialisé pour `HookAgent` et
  `StoryboardAgent`, entraîné sur les sorties validées. Diviserait le coût par ~5 sur les
  agents à fort volume — mais n'a de sens qu'au-delà de ~50 000 générations.
- **Auto-optimisation des prompts** (DSPy / évolution guidée par métriques), avec les
  évals existantes comme garde-fou.
- **Publication programmée intelligente** selon l'audience réelle de chaque compte.
- **White-label** pour agences.

## 5. Évolutions techniques (déclenchées par des seuils, pas par le calendrier)

| Déclencheur | Évolution |
|---|---|
| p95 de latence de rendu > 3 min | 2ᵉ VPS-MEDIA, puis encodage NVENC sur GPU |
| > 500 jobs/jour | PostgreSQL managé + PgBouncer |
| > 10 M lignes dans `job_events` | partitionnement mensuel + archive Parquet sur R2 |
| Besoin d'analytique lourde | ClickHouse pour `usage_events` et `publication_metrics` |
| Pipelines > 10 types | migration du moteur vers Temporal |
| Équipe > 3 personnes | Vault/Infisical, environnement de staging complet, IaC (Terraform) |
| Clients entreprise | SSO SAML, résidence des données, SLA contractuel, SOC 2 |
| > 100 k documents en mémoire sémantique | index vectoriel dédié (Qdrant) si pgvector sature |

## 6. Roadmap de mise en œuvre

### Phase 0 — Avant la moindre ligne de code (1 semaine)
- [ ] Lancer les demandes d'accès aux API TikTok / Instagram / YouTube (délai le plus long — R3).
- [ ] Produire **20 vidéos manuellement** avec ffmpeg et des assets IA. Identifier ce qui rend une vidéo bonne (R5).
- [ ] Valider juridiquement le positionnement « ADN viral » (R2) et la stratégie d'ingestion (R1).
- [ ] Valider cette architecture.

### Phase 1 — Walking skeleton (3 semaines)
Objectif : **une vraie vidéo, de bout en bout, en production**. Pas une démo.
- 6 agents seulement : Concept, Script, Storyboard, Image, Voice, Render.
- Moteur de pipeline + checkpoints + `job_steps`. **Dès le départ** — c'est le socle.
- 1 gate HITL (script). PostgreSQL, Redis, R2, ffmpeg.
- Aucun n8n, aucun cache sémantique, aucun ADN.
- Model Registry et Prompt Registry en version minimale mais **avec leurs interfaces définitives**.

### Phase 2 — ADN viral (3 semaines)
- Agents A1–A5, B1–B4. Upload de fichier comme chemin principal.
- Bibliothèque d'ADN + pgvector. Visualisation d'ADN dans l'UI.
- Pipeline de transfert. Gates G2 et G3.

### Phase 3 — Production-ready (3 semaines)
- Cache L1–L3 + L5, disjoncteurs, dead letters, watchdog.
- Observabilité complète, garde-fous de budget, RLS multi-tenant.
- n8n : WF-05, WF-10, WF-11, WF-12, WF-14.
- Stripe, crédits, plans.

### Phase 4 — Distribution (2–3 semaines, dépend de R3)
- Export assisté d'abord ; publication automatique au fil des approbations d'API.
- WF-06, WF-07, WF-08, WF-09. Collecte de métriques et boucle de feedback.

### Phase 5 — Passage à l'échelle (continu)
- Évals de prompts en CI, canary, tuning des coûts, 2ᵉ VPS-MEDIA, cache sémantique sélectif.

**Total jusqu'à un SaaS commercialisable : ~12 semaines.**

## 7. Ce que je referais différemment si le budget était de 300 €/mois

Utile pour comprendre ce qui est contraint par l'argent et ce qui est un vrai choix
d'architecture :

- PostgreSQL managé avec PITR (supprime le risque irréversible n°1) — **je le ferais en premier**.
- ElevenLabs par défaut : la voix est le premier facteur de qualité perçue.
- Remotion pour le rendu : compositions React, itération visuelle bien plus rapide.
- Un vrai environnement de staging.
- Temporal Cloud si les pipelines se diversifient.

**Ce que je ne changerais pas, à aucun budget** : la séparation des plans, le contrat
d'agent unique, les registries de prompts et de modèles, l'adressage par contenu, la
machine à états sur PostgreSQL, les gates comme objets du domaine. Ce sont ces éléments
qui font tenir le système à l'échelle — ils ne coûtent rien de plus.
