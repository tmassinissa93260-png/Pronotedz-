# Ancre — Concept produit (v0.1)

*Document de travail — nom provisoire "Ancre". À valider.*

## 1. Résumé exécutif

Application mobile (iOS/Android) qui combat le scroll compulsif en s'attaquant aux mécanismes scientifiquement documentés qui le causent — dopamine à renforcement variable, absence de point d'arrêt, effets physiques (cou, pouce) — plutôt qu'en imposant un simple minuteur ou blocage total comme les solutions existantes.

**Différenciateur central : premier produit 100% francophone du secteur, avec chaque fonctionnalité reliée explicitement à l'étude scientifique qui la justifie.**

## 2. Le problème (rappel synthétique)

- Le scroll infini exploite un circuit de renforcement variable (dopamine) — mécanisme proche des machines à sous.
- 52-64% des utilisateurs (UK/US, sondages 2022-2025) se déclarent "accros au scroll" ; jusqu'à 82-86% chez la Gen Z.
- Effets mesurés : baisse de fonction exécutive après une seule session, réduction de la capacité cognitive par la simple présence du téléphone (étude UT Austin), anxiété existentielle liée au doomscrolling.
- Effets physiques documentés : "text neck" (charge cervicale jusqu'à ~22 kg à 45° d'inclinaison), ténosynovite de De Quervain / "texting thumb" (jusqu'à 60% de plaintes dans certaines cohortes ado), troubles du sommeil liés à la lumière bleue.
- Détail complet et sources : voir `docs/recherche-scrolling.md` (recherche menée en amont de ce document).

## 3. Paysage concurrentiel

| Produit | Approche | Marché | Limite |
|---|---|---|---|
| Opal | Blocage niveau VPN, sessions "Deep Focus" | US, anglophone | Pas de volet physique, pas de justification scientifique affichée |
| One Sec | Friction (pause/respiration) avant ouverture | US, anglophone | Ne bloque rien réellement, pas de détection comportementale |
| Freedom | Blocage cross-device synchronisé | US, anglophone | Rigide, taux de contournement élevé |
| Forest | Gamification (arbre qui pousse) | Global mais UX US | Motivation superficielle, aucun ancrage scientifique |
| ScrollGuard | Ciblé Reels/Shorts | US, anglophone | Un seul angle (vidéo courte) |

**Constat clé : tous ces outils sont déjà téléchargeables en France (pas de blocage géographique) — le vide n'est donc pas dans la disponibilité, mais dans la localisation, le positionnement scientifique et le volet ergonomique/physique.**

## 4. Solution : mécanisme → contre-mesure

| Mécanisme scientifique | Contre-mesure produit |
|---|---|
| Renforcement variable / anticipation dopaminergique | Aperçu neutre du contenu avant l'ouverture du flux (nombre de posts, sujet dominant) pour désamorcer l'anticipation |
| Absence de point d'arrêt (scroll infini) | Friction progressive : pause automatique toutes les X minutes, compteur de scrolls visible |
| Anxiété liée au doomscrolling | Détection de pattern (vitesse de scroll + heure + type de contenu), pas seulement un chrono |
| Présence physique du téléphone | Rituel/objet complémentaire (pochette, mode "hors de portée") — hors périmètre logiciel pur |
| Text neck / texting thumb | Rappels ergonomiques contextuels via capteurs (gyroscope/accéléromètre) |
| Lumière bleue / sommeil | Non traité — déjà couvert nativement par iOS/Android (Night Shift, Wind Down), pas un axe différenciant |

## 5. Contraintes techniques réelles — section critique

Cette partie doit être lue avant tout chiffrage : **les deux plateformes ne permettent pas la même chose**, et l'écart change ce que "MVP" veut dire.

### iOS
- Le contrôle d'usage passe exclusivement par les frameworks **FamilyControls / ManagedSettings / DeviceActivity** (Screen Time API, depuis iOS 16).
- Apple exige une **entitlement privilégiée validée manuellement** pour publier une app utilisant FamilyControls sur l'App Store — délai et risque de refus à anticiper.
- Ces frameworks donnent des **seuils de temps par catégorie/app** (ex: "bloquer Instagram après 20 min"), pas d'accès au contenu ni aux gestes à l'intérieur d'une autre app.
- **Conséquence : la détection de "vitesse de scroll" en temps réel dans Instagram/TikTok n'est pas possible sur iOS.** Le sandboxing d'Apple l'interdit structurellement, quel que soit le talent technique.

### Android
- **UsageStatsManager** donne des statistiques d'usage (temps par app) — équivalent fonctionnel de DeviceActivity, permission utilisateur simple.
- **AccessibilityService** peut recevoir les événements système, y compris `TYPE_VIEW_SCROLLED` dans n'importe quelle app — donc la détection de pattern de scroll **est technique possible sur Android**.
- Mais AccessibilityService est un permission sensible : forte méfiance utilisateur ("accès total à l'écran"), et Google Play scrutinise étroitement les apps qui l'utilisent hors accessibilité réelle (les apps de blocage de distraction sont un usage toléré et documenté, mais l'app peut être flaguée en review).

### Ce que ça change concrètement
La fonctionnalité "détection de pattern doomscrolling" présentée en section 4 **n'est donc pas symétrique** : réalisable en profondeur sur Android, réduite à des seuils de temps par catégorie sur iOS. Le MVP doit soit accepter cette asymétrie (Android = version complète, iOS = version "seuils"), soit repousser cette fonctionnalité à une V2 et démarrer sur ce que les deux plateformes permettent nativement (friction + rappels ergonomiques + seuils de temps).

### Rappels ergonomiques (cou/pouce)
- Faisables via CoreMotion (iOS) / SensorManager (Android), mais l'accès aux capteurs de mouvement **en arrière-plan est restreint sur iOS** (exécution background limitée). Réaliste seulement quand l'app est au premier plan, ou via un rappel périodique déclenché par DeviceActivity plutôt qu'un monitoring continu.

## 6. MVP révisé (réaliste, cross-platform dès V1)

1. **Friction progressive** basée sur seuils de temps/catégorie (FamilyControls sur iOS, UsageStatsManager sur Android) — pas de scroll-tracking en V1.
2. **Rappels ergonomiques** déclenchés à intervalle fixe quand l'app est active (pas de monitoring background continu).
3. **Tableau de bord scientifique** : chaque statistique affichée renvoie à la source qui la justifie.

→ **Détection fine du pattern de scroll (vitesse/contenu) : fonctionnalité Android-only, en V2**, présentée comme un "mode avancé" plutôt qu'un socle du produit, pour ne pas dépendre d'une asymétrie iOS/Android dès le lancement.

## 6bis. Flux utilisateur détaillé — friction escaladée + redirection

Flux validé avec l'utilisateur, à implémenter dès le MVP :

1. **Ouverture d'une app surveillée (ex. TikTok)** → écran d'attente de **30 secondes**, avec un rappel scientifique qui défile (ex. "tu es dans la phase d'anticipation dopaminergique, pas la récompense").
2. **Accès accordé** → l'app annonce le budget de session : **10 minutes par défaut** (choisi plutôt que 15 : cohérent avec la limite "usage continu <20 min" documentée pour l'œil/les TMS, et une durée courte crée plus d'occasions de "gagner" en sortant avant la limite).
3. **Budget de 10 min atteint** → fermeture forcée de l'app surveillée (shield réappliqué).
4. **Tentative de réouverture immédiate** → attente **2 minutes** (volontairement plus longue que l'attente initiale de 30 sec) : la friction augmente avec l'insistance plutôt que de rester fixe.
5. **Pendant ces 2 minutes** → messages qui alternent entre confrontation directe ("tu devrais être en train de bosser") et reformulation positive orientée action ("il fait beau, va faire du foot ?"). Doser vers plus de messages positifs que de messages culpabilisants : la littérature sur le changement de comportement montre que la culpabilisation fonctionne à très court terme mais augmente le taux de désinstallation par rapport à des messages orientés action.
6. **Retour dans l'app après les 2 minutes** → au lieu de renvoyer directement vers l'app surveillée, écran de proposition d'alternative (lecture, documentaire, activité) tirée du **questionnaire de centres d'intérêt rempli à la première utilisation** (onboarding).

### Contrainte technique sur ce flux

L'écran système de blocage d'Apple (`ManagedSettings` shield) est un template figé : titre, sous-titre, icône, couleur, et jusqu'à 2 boutons — pas de compte à rebours dynamique ni de messages qui changent seuls. Le compte à rebours (30 sec, puis 2 min) et la rotation des messages doivent donc être affichés **dans l'app elle-même**, ouverte via l'action d'un bouton du shield (`ShieldActionExtension`) plutôt que dans l'écran système. Aucun impact sur la faisabilité globale, juste sur l'endroit où vit l'UI.

## 6ter. Questionnaire d'onboarding et catalogue d'alternatives

Rempli à la première ouverture, avant toute activation du blocage. Objectif : construire un profil d'intérêts pour alimenter l'écran de redirection (étape 6 du flux ci-dessus).

**Questions (choix multiples, 3-5 réponses max par catégorie pour ne pas décourager) :**
1. Qu'est-ce que tu lirais si tu avais plus de temps ? (romans, essais, BD, presse, rien pour l'instant)
2. Quel type de documentaire/vidéo longue tu regarderais volontiers ? (sciences, histoire, sport, société, aucun)
3. Quelle activité physique te tente le plus en ce moment ? (course, foot, muscu, marche, aucune)
4. Tu préfères sortir plutôt seul(e) ou avec quelqu'un quand tu décroches de l'écran ?

**Catalogue d'alternatives (mappé aux réponses) :**
- Chaque tag d'intérêt (ex. "sport/foot") est relié à 2-3 suggestions concrètes stockées localement (nom, type, courte description) — pas besoin d'API externe pour le MVP, un catalogue statique suffit.
- L'écran de redirection tire 2-3 suggestions aléatoires parmi celles correspondant aux tags cochés, jamais les mêmes deux fois de suite.
- Une échappatoire existe toujours vers l'app surveillée (pas un blocage total après la redirection) mais avec un léger rappel visuel ("tu peux toujours scroller, mais...") pour ne pas transformer l'app en prison et risquer la désinstallation.

## 7. Modèle économique (pistes)

- Freemium : friction de base + dashboard gratuits, rappels ergonomiques + mode avancé Android en payant.
- B2B2C : licences écoles/entreprises (médecine du travail, prévention TMS) — angle différenciant vs concurrents US positionnés grand public pur.
- Positionnement prix marché français (moins saturé de comparables locaux que le marché US).

## 8. Risques à ne pas sous-estimer

- Validation de l'entitlement FamilyControls par Apple : délai variable, refus possible sans justification claire.
- Asymétrie iOS/Android peut complexifier le message marketing ("le produit ne fait pas pareil selon le téléphone").
- AccessibilityService sur Android : risque de retrait Play Store si l'usage est jugé disproportionné vs la finalité déclarée.
- Marché : la "corruption" ou un blocage réglementaire évoqués initialement ne sont pas fondés (voir échange précédent) — le vrai obstacle est la localisation et l'exécution, pas une barrière externe.

## 9. Sources scientifiques

Voir bibliographie complète dans la recherche menée en amont (section recherche du fil de discussion), notamment :
- Sharpe & Spooner, *Dopamine-scrolling: a modern public health challenge*, J R Soc Med, 2025.
- Nature Scientific Reports, *The mere presence of a smartphone reduces basal attentional performance*, 2023.
- PMC, *Prevalence of De Quervain's Tenosynovitis among Teenage Mobile Users*, 2025.
- PMC/Cureus, *Assessing the Impact of Smartphone Use on Neck Pain*, Jeddah, 2024.
- Apple Developer Documentation — FamilyControls, ManagedSettings, DeviceActivity (WWDC21/22).
- Android Developer Documentation — UsageStatsManager, AccessibilityService.

## 10. Prochaines étapes proposées

1. Valider ou changer le nom provisoire "Ancre".
2. Décider : lancement Android-first (fonctionnalité complète immédiate) ou iOS+Android simultané (MVP réduit commun) ?
3. ~~Si "GO" : je pose la structure de projet et code le MVP de la section 6.~~ **Fait pour iOS** : squelette Swift/SwiftUI dans `ios-app/` (voir `ios-app/README-SETUP.md` pour les étapes restantes côté Xcode — entitlement Family Controls, App Groups, targets d'extension — qui ne peuvent pas être faites depuis ce dépôt).
4. Reste à faire : version Android (Kotlin, `AccessibilityService` + `UsageStatsManager`), et ouverture réelle du projet iOS dans Xcode sur un Mac pour compiler/tester ce qui a été écrit ici à l'aveugle.
