# 12 — Registre des risques

Notation : **Impact** × **Probabilité** → **Criticité**.
Les risques sont triés par criticité décroissante. Les quatre premiers peuvent tuer le projet.

---

## <a id="r1"></a>R1 — Ingestion TikTok : légalité et fragilité 🔴 CRITIQUE

**Impact** : bloquant (F2, F3, F4 — soit 3 des 7 fonctionnalités). **Probabilité** : élevée.

Le téléchargement de vidéos TikTok via `yt-dlp` viole les CGU de TikTok. Techniquement,
c'est aussi le composant le plus fragile de toute la chaîne : TikTok modifie ses
protections régulièrement, et un scraper cassé bloque le produit du jour au lendemain.
Le risque n'est pas seulement juridique : c'est aussi un risque d'**exploitation quotidienne**.

**Mitigations, dans l'ordre de préférence :**
1. **Chemin principal recommandé** : l'utilisateur **téléverse un fichier** qu'il a
   téléchargé lui-même, ou fournit une vidéo dont il détient les droits. Le SaaS ne
   télécharge rien. Cela déplace la responsabilité et supprime la dépendance technique.
2. Analyser **ses propres** vidéos via l'API officielle TikTok (compte connecté) — légitime.
3. Coller **le transcript et les métadonnées** manuellement : dégradé mais légal et robuste.
4. Isoler l'`IngestAgent` derrière une interface stricte pour pouvoir changer de stratégie
   sans toucher au reste (déjà prévu dans l'architecture).
5. CGU explicites : l'utilisateur déclare détenir les droits ; journalisation des sources.

> **Recommandation** : construire F2/F3/F4 sur l'**upload** en v1. Le scraping d'URL
> est une commodité à évaluer avec un conseil juridique, pas une fondation.

---

## <a id="r2"></a>R2 — Transfert d'ADN et propriété intellectuelle 🔴 CRITIQUE

**Impact** : élevé (réputation, litige). **Probabilité** : moyenne.

Vendre « copie l'ADN d'une vidéo virale » peut être perçu — ou pratiqué — comme du
plagiat industrialisé. Juridiquement, un *style* et une *structure* ne sont pas
protégeables ; un script, un visuel ou une phrase le sont.

**Mitigations :**
- `DNAAbstractorAgent` (B2) **obligatoire et non contournable** : ce qui est stocké et
  réutilisé est un squelette (durées, courbes, patrons), jamais du contenu.
- `PolicyAgent` (E2) mesure la **similarité sémantique** entre la sortie et la source ;
  au-delà d'un seuil, le job est bloqué et l'étape régénérée.
- Aucune phrase du transcript source ne peut apparaître dans un champ de patron
  (assertion déterministe dans les évals du prompt d'extraction).
- Positionnement produit : « apprendre des structures qui performent », pas « cloner ».
- Sujet à valider avec un juriste avant la mise en marché.

---

## <a id="r3"></a>R3 — Accès aux API de publication 🔴 CRITIQUE pour F7

**Impact** : bloquant pour la publication. **Probabilité** : élevée.

L'accès à la TikTok Content Posting API demande une **validation d'application** (semaines
à mois, refus possible). Le quota YouTube (10 000 unités/jour, ~1 600 par upload) limite
à ~6 vidéos/jour toutes organisations confondues sans extension de quota. Instagram exige
un compte Business relié à une Page.

**Mitigations :**
- **Lancer les demandes de validation dès le jour 1**, avant même d'écrire du code : c'est
  le chemin critique le plus long du projet.
- v1 : **export + publication assistée** (téléchargement du MP4 + copy prête à coller,
  rappel programmé). Fonctionnel, sans dépendance d'approbation.
- Publication automatique en v1.5, plateforme par plateforme, au fil des approbations.
- Demander l'extension de quota YouTube tôt (délai long également).
- Architecture : un adapter par plateforme, activable indépendamment.

---

## <a id="r4"></a>R4 — Dérapage des coûts IA 🔴 CRITIQUE (budget 80 €)

**Impact** : élevé. **Probabilité** : élevée sans garde-fous.

Une boucle de retry mal bornée, un `max_tokens` oublié ou un utilisateur qui lance 500
jobs peut consommer le budget mensuel en une nuit.

**Mitigations** : budget par job / par org / global, coupure dure à 95 %, `max_tokens`
toujours explicite, plafond global de tentatives par job, alerte P1 avec coupure
automatique, cache multi-niveaux, revue hebdomadaire du coût par vidéo.
Détail en [10-budget.md](./10-budget.md#5-garde-fous-budgétaires).

---

## R5 — Qualité vidéo insuffisante 🟠 ÉLEVÉ

**Impact** : élevé (le produit ne se vend pas). **Probabilité** : moyenne à élevée.

Le risque produit le plus sous-estimé : un enchaînement d'images IA fixes avec une voix
TTS et des sous-titres ne « ressemble » pas à une vidéo TikTok performante. Le montage
généré peut être techniquement correct et commercialement inutilisable.

**Mitigations** : mouvement Ken Burns systématique, coupes alignées sur le beat (données
de l'`AudioAgent`), sous-titres karaoké mot à mot, b-roll de stock (Pexels/Pixabay) mêlé
aux images IA, seed cohérente pour l'unité visuelle, gates HITL qui laissent l'humain
corriger. **Et surtout : produire 20 vidéos manuellement avant d'écrire le pipeline**,
pour savoir ce qui fait la différence. C'est un travail de direction artistique, pas
d'architecture.

---

## R6 — Charge CPU du rendu 🟠 ÉLEVÉ

**Impact** : moyen (latence, SLO). **Probabilité** : élevée à la montée en charge.

Le rendu ffmpeg est CPU-bound : ~45 s pour 30 s de vidéo sur 4 vCPU dédiés → ~8 rendus
simultanés max, ~120 vidéos/heure sur un VPS-MEDIA.

**Mitigations** : preset `veryfast` + CRF 23, file de rendu dédiée avec concurrence
plafonnée, réutilisation des segments par hash (un re-render de sous-titres ne réencode
pas la vidéo), workers sans état pour scaler horizontalement, métrique de saturation
avec alerte P2, encodage matériel (NVENC) quand un GPU sera disponible.

---

## <a id="r7"></a>R7 — Charge d'exploitation de l'auto-hébergement 🟠 ÉLEVÉ

**Impact** : moyen à élevé. **Probabilité** : élevée.

Auto-héberger PostgreSQL, Redis, n8n, Grafana, Loki et Langfuse pour économiser
~275 €/mois transfère le coût sur le temps humain : sauvegardes, mises à jour de
sécurité, saturation disque, incidents nocturnes. C'est le vrai prix des 80 €.

**Mitigations** : tout en Docker Compose versionné ; **sauvegardes PostgreSQL testées
par restauration réelle chaque semaine** (une sauvegarde jamais restaurée n'existe pas) ;
snapshots Hetzner ; purge automatique des exécutions n8n et des artefacts ;
alerte disque à 80 % ; runbooks écrits ; PostgreSQL managé dès que le budget passe à 150 €.

---

## R8 — Licences 🟡 MOYEN

- **n8n** : licence *Sustainable Use* (fair-code). L'usage interne pour opérer son propre
  SaaS est autorisé ; **revendre n8n ou l'exposer comme fonctionnalité à ses clients ne
  l'est pas**. Ici n8n est un outil interne, invisible des clients → conforme. À ne pas
  faire dériver.
- **Remotion** : licence entreprise requise pour un SaaS → écarté en v1 ([ADR-004](./adr/004-moteur-rendu.md)).
- **Polices** : vérifier chaque licence pour l'incorporation dans une vidéo commerciale.
- **Musique** : n'utiliser que des banques explicitement libres de droits commerciaux, avec traçabilité de la source par piste.

---

## R9 — Modération de contenu et conformité IA 🟡 MOYEN

Le service peut générer de la désinformation, du contenu médical/financier dangereux ou
du contenu inapproprié, publié automatiquement sous le nom de l'utilisateur.

**Mitigations** : `PolicyAgent` (E2) systématique avant tout gate final ; catégories
interdites configurables par org ; marquage « contenu généré par IA » (obligation
plateformes + AI Act) ; gates HITL par défaut activés ; `audit_logs` avec rétention
1 an ; CGU claires sur la responsabilité éditoriale de l'utilisateur.

---

## R10 — Dépendance à Anthropic 🟡 MOYEN

Concentration sur un fournisseur pour les agents créatifs et d'analyse.
**Mitigations** : le Model Registry rend le basculement déclaratif ; les prompts sont
testés sur au moins deux familles de modèles dans les évals ; OpenRouter en secours
immédiat ; les sorties structurées passent par un mécanisme portable (JSON Schema), pas
par une fonctionnalité propriétaire.

---

## R11 — Complexité excessive pour un MVP 🟡 MOYEN

18 agents, 17 workflows, 5 niveaux de cache, 5 types de mémoire : c'est une architecture
cible, pas un périmètre de sprint 1. Le risque est de passer trois mois sur l'infrastructure
sans jamais produire une vidéo regardable.

**Mitigation** : la roadmap de [13-evolutions.md](./13-evolutions.md) impose un **walking
skeleton en 3 semaines** — 6 agents, 0 workflow n8n, 1 niveau de cache, 1 gate — qui
produit une vraie vidéo de bout en bout. Le reste s'ajoute sur ce squelette. Les
interfaces décrites ici existent dès le départ ; leurs implémentations riches arrivent après.

---

## R12 — Fuite inter-tenant 🟡 MOYEN mais impact critique s'il se réalise

Un bug de cache ou une requête sans filtre `org_id` expose le contenu d'un client à un autre.
**Mitigations** : RLS PostgreSQL (défense indépendante du code applicatif), `org_id`
encodé dans les clés de cache, préfixe R2 par org, URLs signées à durée courte, test
d'intégration multi-tenant obligatoire dans la CI.

---

## R13 — Latence perçue 🟢 FAIBLE

6 à 12 minutes est long face à une UI moderne. **Mitigations** : streaming SSE de la
progression, aperçus progressifs (script → storyboard → images → vidéo), notification
push à la fin, cadrage des attentes dès l'onboarding. Le temps est acceptable s'il est
*visible*.

---

## Synthèse — les 4 décisions qui débloquent le plus de risque

1. **Faire de l'upload le chemin principal de F2** (R1) — supprime le risque juridique et technique n°1.
2. **Lancer les demandes d'accès aux API sociales immédiatement** (R3) — c'est le délai le plus long, il court en parallèle.
3. **Câbler les garde-fous de budget avant le premier appel LLM en production** (R4).
4. **Produire 20 vidéos à la main avant d'écrire le pipeline** (R5) — c'est ce qui détermine si le produit vaut quelque chose.
