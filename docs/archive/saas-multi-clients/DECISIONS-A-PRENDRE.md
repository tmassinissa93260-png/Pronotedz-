# Décisions — état

Mis à jour le 2026-08-05. Les 4 décisions bloquantes sont **prises**.

---

## ✅ Décisions validées

### 1. Ingestion des vidéos sources → **les deux**
Upload de fichier par défaut, collage de lien en option avec avertissement explicite.

**Conséquences appliquées** : `IngestAgent` a deux stratégies derrière la même interface
(`UploadStrategy`, `UrlStrategy`) ; l'option lien est désactivable par un flag global —
si TikTok casse le téléchargement ou si le conseil juridique le déconseille, on coupe
l'option sans rien changer d'autre. Case à cocher obligatoire « je détiens les droits »,
horodatée et journalisée dans `audit_logs`. Détail : [15-ingestion.md](./15-ingestion.md).

### 2. Publication → **export assisté en v1**
L'app fournit le MP4 + la légende + les hashtags prêts à coller, avec rappel programmé.
Publication automatique plateforme par plateforme, au fil des approbations d'API.

**Conséquences appliquées** : WF-06 devient `export-assist` ; la publication automatique
passe en phase 4bis. Les demandes d'accès aux API restent à déposer immédiatement — elles
courent en parallèle sans bloquer le lancement.

### 3. Voix → **gratuite par défaut, premium pour les comptes payants**
Kokoro-82M local pour les plans gratuit et starter ; ElevenLabs pour Pro et Agency.

**Conséquences appliquées** : l'abonnement ElevenLabs (22 €) n'entre au budget qu'à
partir du premier client payant — il est financé par le revenu, pas par les 80 € de départ.
Règle de routage déjà prévue dans `models.yaml`.

### 4. Cible → **agences et community managers** 🔴 *impact majeur*
100+ vidéos/mois, plusieurs marques clientes, travail en équipe.

**Conséquences appliquées** : c'est la décision qui change le plus l'architecture.
Elle a son document dédié : **[14-cible-agences.md](./14-cible-agences.md)**.
En résumé — hiérarchie `workspace → marque → projet → job` au lieu de `org → projet`,
génération en lot en v1 (plus « plus tard »), double validation interne puis client,
lien d'approbation client sans création de compte, et une économie unitaire à revoir.

---

## ⏳ Décisions restantes (non bloquantes)

### 5. 🟡 Durée cible des vidéos
15–20 s, 30–45 s, ou 60 s+ ? Impacte le nombre de scènes, le coût unitaire (×2 à ×3 entre
20 s et 60 s) et la structure de l'ADN.
**Hypothèse de travail retenue : 30 s, 8 scènes.** Modifiable sans refonte.

### 6. 🟡 Langue
**Hypothèse retenue : FR + EN.** Chaque langue ajoutée demande sa propre suite d'évals
de prompts. Kokoro est meilleur en anglais qu'en français — c'est un argument de plus
pour ElevenLabs sur les plans payants.

### 7. 🟡 Modèle tarifaire
Le schéma supporte les trois approches. Avec la cible agence, je recommande :
**abonnement par siège + quota de vidéos par marque + crédits additionnels à l'achat.**
À confirmer, mais ça n'empêche pas de démarrer — voir [14-cible-agences.md](./14-cible-agences.md#6-économie).

### 8. 🟡 Positionnement « ADN viral »
Décision technique déjà prise et implémentée dans l'architecture (le `DNAAbstractorAgent`
garantit qu'on ne stocke jamais le contenu d'un tiers, seulement une structure).
Reste **l'avis juridique** sur la formulation commerciale. À lancer cette semaine.

### 9. 🟢 Taille de l'équipe
Impacte la vitesse de la roadmap et le seuil de bascule vers Remotion (gratuit ≤ 3 personnes).
Sans réponse, je suppose **1 à 2 personnes** — donc une roadmap de 12 semaines et un
auto-hébergement à garder aussi simple que possible.

---

## Les deux choses à lancer cette semaine (en parallèle, sans bloquer)

1. **Déposer les demandes d'accès aux API** TikTok Content Posting, Instagram Graph,
   YouTube Data v3 (+ extension de quota). Délai : plusieurs semaines. Ça ne bloque plus
   le lancement grâce à la décision 2, mais plus tôt c'est déposé, plus tôt c'est utilisable.
2. **Avis juridique** sur la formulation commerciale de l'« ADN viral » et sur l'option
   « collage de lien » de la décision 1.

## Suite immédiate

L'architecture est à jour avec tes 4 réponses. **Prochaine étape : ton feu vert pour
démarrer la phase 1** — le squelette fonctionnel (voir [13-evolutions.md](./13-evolutions.md#6-roadmap-de-mise-en-œuvre)).
