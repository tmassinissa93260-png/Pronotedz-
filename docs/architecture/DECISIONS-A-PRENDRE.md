# Décisions à prendre avant de coder

Neuf points que je ne peux pas trancher seul : ils dépendent de ton marché, de ton
appétence au risque ou d'un avis juridique. Ils sont classés par urgence.

---

### 1. 🔴 Stratégie d'ingestion des vidéos sources — **bloquant pour F2/F3/F4**

| Option | Légalité | Robustesse | Friction utilisateur |
|---|---|---|---|
| **A** — Upload de fichier uniquement (recommandé) | ✅ | ✅ | moyenne |
| **B** — Coller une URL, téléchargement par le serveur | ⚠️ viole les CGU TikTok | ❌ fragile | faible |
| **C** — Analyser uniquement ses propres vidéos via l'API officielle | ✅ | ✅ | dépend de l'approbation d'API |
| **D** — A + B, B présenté comme « à vos risques » | ⚠️ | ⚠️ | faible |

Ma recommandation : **A pour la v1**, C en complément, B seulement après avis juridique.
Voir [R1](./12-risques.md#r1).

---

### 2. 🔴 Publication automatique ou export assisté en v1 ?

L'accès à la TikTok Content Posting API demande une validation de plusieurs semaines,
avec un risque de refus. Deux stratégies :
- **Export assisté** : MP4 + copy prête à coller + rappel programmé. Livrable immédiatement.
- **Attendre l'approbation** : bloque la feature F7 pour une durée inconnue.

Ma recommandation : **export assisté en v1**, publication automatique en v1.5.
Dans les deux cas, **déposer les demandes d'accès dès cette semaine**.

---

### 3. 🟠 Voix : Kokoro local ou ElevenLabs ?

ElevenLabs = 22 €/mois, soit **27 % du budget total**, mais c'est le facteur de qualité
perçue n°1 sur une vidéo courte. Kokoro est gratuit et honnête, pas excellent.

Options : (a) Kokoro partout ; (b) Kokoro en gratuit / ElevenLabs en payant ;
(c) ElevenLabs partout, en réduisant le VPS-MEDIA.

Ma recommandation : **(b)** — ça finance la qualité par le revenu.

---

### 4. 🟠 Positionnement du produit sur l'« ADN viral »

Le vocabulaire choisi a des conséquences juridiques et réputationnelles réelles.

- « Clone les vidéos virales » → maximum d'attrait, maximum de risque.
- « Apprends des structures qui performent » → sûr, moins accrocheur.
- « Analyse tes propres vidéos performantes et réplique ce qui marche » → sûr, valeur claire, marché plus étroit.

Ma recommandation : la formulation intermédiaire, avec le `DNAAbstractorAgent` comme
garantie technique de la promesse. À valider avec un juriste ([R2](./12-risques.md#r2)).

---

### 5. 🟠 Cible utilisateur — elle change le produit

- **Créateur solo** : simplicité, gates par défaut, 10–30 vidéos/mois.
- **Agence / social media manager** : multi-marques, batch, revue en équipe, 100+ vidéos/mois.
- **E-commerce / marque** : catalogue produit, cohérence de marque forte.

Cela détermine la priorité des évolutions (presets multi-marques, batch, collaboration)
et la structure tarifaire. Je n'ai pas cette information.

---

### 6. 🟡 Durée cible des vidéos

15–20 s, 30–45 s ou 60 s+ ? Impacte le nombre de scènes, le coût unitaire (× 2 à 3 entre
20 s et 60 s), le temps de rendu et la structure de l'ADN.
Hypothèse retenue dans ce document : **30 s, 8 scènes**.

---

### 7. 🟡 Langue

FR seul, FR+EN, ou multilingue ? Impacte les prompts (une suite d'évals par langue),
la qualité TTS (Kokoro est meilleur en anglais) et la taille du marché.
Hypothèse retenue : **FR + EN**.

---

### 8. 🟡 Modèle tarifaire

Crédits à l'usage, abonnement à quota, ou hybride ? Le schéma de base supporte les trois
(`credit_ledger` + `plans`), mais l'UI, les garde-fous et le funnel d'onboarding diffèrent.
Hypothèse retenue : **abonnement avec quota mensuel + achat de crédits additionnels**.

---

### 9. 🟢 Équipe

Solo, ou plusieurs personnes ? Cela change :
- la licence n8n (fair-code : usage interne OK dans tous les cas ici) ;
- le seuil de bascule vers Remotion (≤ 3 personnes = gratuit) ;
- la faisabilité de l'auto-hébergement ([R7](./12-risques.md#r7)) ;
- la vitesse d'exécution de la roadmap des 12 semaines.

---

## Ce que je propose comme suite

1. Tu réponds aux points **1, 2, 3, 4** (les bloquants).
2. J'ajuste l'architecture en conséquence — notamment les documents 03, 04 et 10.
3. Tu valides.
4. On démarre la **phase 1** : le walking skeleton (6 agents, une vraie vidéo de bout en bout, 3 semaines).

Aucune ligne de code applicatif ne sera écrite avant l'étape 3.
