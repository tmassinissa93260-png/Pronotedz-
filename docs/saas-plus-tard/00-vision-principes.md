# 00 — Vision & principes directeurs

## 1. Ce que le produit fait

| # | Fonctionnalité | Entrée | Sortie |
|---|---|---|---|
| F1 | Vidéo depuis une idée | texte libre | MP4 9:16 + sous-titres + métadonnées |
| F2 | Analyse d'une vidéo TikTok | URL ou fichier | rapport d'analyse structuré |
| F3 | Extraction de l'ADN viral | vidéo analysée | objet `ViralDNA` (JSON versionné) |
| F4 | Transfert d'ADN | `ViralDNA` + nouveau sujet | vidéo au même « squelette », contenu 100 % différent |
| F5 | Validation humaine | job en cours | approbation / rejet / édition à chaque *gate* |
| F6 | Génération d'assets | script | prompts images, images, voix, sous-titres, montage |
| F7 | Publication multi-réseaux | vidéo validée | posts TikTok / IG / YT / (X, LinkedIn) |

## 2. Principes directeurs

Ces principes tranchent tous les arbitrages du reste du document.

### P1 — L'état vit en base, jamais dans l'orchestrateur
n8n, ARQ, un agent, un worker : tous sont **sans état**. La vérité est dans PostgreSQL.
Conséquence directe : n'importe quel composant peut mourir à n'importe quel moment,
la reprise est possible. C'est ce qui rend la reprise automatique (F5 du cahier des
charges) réellement fiable et pas cosmétique.

### P2 — Tout est idempotent et adressé par contenu
Chaque étape produit un artefact dont la clé est `sha256(inputs_normalisés + version_prompt + version_modèle)`.
Rejouer une étape avec les mêmes entrées ne coûte rien et ne produit pas de doublon.
C'est le socle commun du **cache** ([08](./08-cache.md)) *et* de la **reprise** ([07](./07-fiabilite.md)) —
un seul mécanisme, deux bénéfices.

### P3 — Aucun fournisseur IA n'est mentionné dans la logique métier
Un agent demande une *capacité* (`text.reason`, `image.generate`, `audio.tts`),
jamais un fournisseur. Le routage est déclaratif ([06](./06-prompts-modeles.md)).
Ajouter un modèle = éditer un YAML. Remplacer ElevenLabs par Kokoro = éditer un YAML.

### P4 — Le prompt est une donnée versionnée, pas du code
Un prompt a un `id`, une `version` semver, un hash, un jeu d'évals et un statut
(`draft` / `canary` / `stable` / `deprecated`). On peut rollback un prompt sans redéployer.

### P5 — Séparer la forme du fond
L'ADN viral capture **la forme** (rythme, structure, prosodie, arc émotionnel).
Le sujet apporte **le fond**. Elles ne se croisent qu'au moment du `DNATransferAgent`.
Cette séparation est à la fois un choix technique (réutilisabilité de l'ADN) et une
**protection juridique** : on ne recopie jamais le contenu d'un tiers ([12](./12-risques.md#r2)).

### P6 — Le coût est une contrainte de premier ordre, pas une optimisation tardive
Chaque appel de modèle passe par un *budget guard* qui connaît le budget restant
du job et du compte. Un job qui dépasse s'arrête proprement au lieu de vider la carte.

### P7 — La validation humaine est un objet du domaine
`approval_gates` est une table, pas un `if`. Un gate a un état, un délai d'expiration,
une politique de repli (`auto_approve` / `auto_reject` / `hold`) et un audit trail.

### P8 — Dégradation gracieuse plutôt qu'échec
Flux Dev indisponible → Flux Schnell. ElevenLabs épuisé → Kokoro local.
Claude Sonnet saturé → Haiku avec prompt renforcé. Le job finit, avec un
`quality_degraded: true` visible par l'utilisateur.

## 3. Non-objectifs (v1)

Explicitement **hors périmètre** pour éviter la dérive :

- Édition vidéo manuelle dans le navigateur (timeline, trim) — on expose un re-render paramétré, pas un éditeur.
- Génération vidéo par modèle (Sora / Veo / Kling) — trop cher pour 80 €/mois. L'interface `video.generate` existe, elle reste débranchée.
- Avatars parlants / lip-sync (HeyGen, D-ID).
- Application mobile native.
- Multi-langue au-delà de FR/EN.
- Marketplace de templates communautaires.

## 4. Objectifs quantifiés (SLO v1)

| Indicateur | Cible |
|---|---|
| Latence bout-en-bout, vidéo 30 s, sans attente humaine | < 6 min p50, < 12 min p95 |
| Latence analyse ADN d'une vidéo TikTok 60 s | < 90 s p95 |
| Taux de jobs terminés sans intervention manuelle | > 95 % |
| Coût médian par vidéo générée | < 0,20 € |
| Disponibilité API | 99,5 % |
| Perte de job après crash worker | 0 (reprise au dernier checkpoint) |
| Concurrence soutenue v1 (1 VPS de rendu) | 8 rendus simultanés, ~120 vidéos/heure |
