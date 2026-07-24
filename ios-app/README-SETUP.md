# Ancre — squelette iOS

Ce dossier contient le code Swift/SwiftUI correspondant à l'architecture décrite dans
`docs/concept-produit.md`. Il a été écrit dans un environnement Linux, **sans Xcode ni
toolchain iOS disponibles** — les fichiers n'ont donc pas pu être compilés ni testés ici.
Les frameworks utilisés (FamilyControls, ManagedSettings, DeviceActivity, SwiftUI pour iOS)
n'existent que sur macOS/Xcode : ouvrir ce projet sur un Mac est une étape obligatoire, pas
une option, avant toute exécution.

## Ce qu'il reste à faire dans Xcode (ne peut pas être fait depuis ce dépôt)

1. Créer un nouveau projet Xcode (App, SwiftUI, iOS 16+ minimum — 17+ recommandé pour
   `DeviceActivityReport` complet).
2. Ajouter ces fichiers au target principal `App/`.
3. Créer 4 targets d'extension (File > New > Target) et y glisser le fichier correspondant :
   - **Shield Configuration Extension** → `ShieldConfigurationExtension/`
   - **Shield Action Extension** → `ShieldActionExtension/`
   - **Device Activity Monitor Extension** → `DeviceActivityMonitorExtension/`
   - **Device Activity Report Extension** → `DeviceActivityReportExtension/`
4. Activer les capacités suivantes sur le target principal (Signing & Capabilities) :
   - **Family Controls** — nécessite une entitlement approuvée manuellement par Apple
     (formulaire développeur, délai variable). Sans cette approbation, l'app ne pourra
     pas être distribuée sur TestFlight/App Store, seulement testée en local.
   - **App Groups** — créer un groupe (ex. `group.com.ancre.app`) et l'ajouter à
     *chaque* target (app + 4 extensions), c'est le seul moyen pour eux de partager
     l'état (`SessionState`, `InterestProfile`).
   - **URL Types** — ajouter un schéma custom (ex. `ancre://`) sur le target principal
     pour permettre à `ShieldActionExtension` de rouvrir l'app sur le bon écran.
5. Remplacer tous les identifiants placeholder (`group.com.ancre.app`, `com.ancre.app`,
   `ancre://`) par les vrais identifiants une fois le compte développeur configuré.

## Design

`App/DesignSystem/Theme.swift` centralise le style (dégradé indigo/violet/bleu, cartes en
verre dépoli `.ultraThinMaterial`, boutons avec retour haptique) inspiré du langage visuel
translucide qu'Apple généralise depuis iOS 26 ("Liquid Glass"). **Non prévisualisé** : sans
simulateur iOS disponible ici, les couleurs/espacements sont un point de départ raisonnable,
pas un résultat validé à l'œil — à ajuster dans Xcode Previews une fois ouvert sur un Mac.

## Ce que ce squelette couvre

- Le flux complet décrit dans `docs/concept-produit.md` section 6bis : attente 30s →
  session (budget décroissant, voir `SessionBudgetPlan.swift`) → fermeture forcée →
  cooldown 2 min → redirection.
- Le "témoin" (accountability partner, `App/Accountability/`) : partage natif d'un
  message pré-rempli vers un contact choisi par l'utilisateur en cas de réouverture forcée.
- L'onboarding et le catalogue d'alternatives (section 6ter).
- La structure des 4 extensions Apple nécessaires au blocage réel.

## Fonctionnalité abandonnée : détection de vitesse de scroll

La détection de pattern de scroll (vitesse/comportement pendant une session TikTok) a été
écartée, y compris via les capteurs de mouvement (CoreMotion) — pas seulement à cause d'une
restriction de vie privée ciblée, mais parce que **l'app ne s'exécute pas du tout** tant
qu'une autre app est au premier plan sur iOS. Aucun capteur, quel qu'il soit, ne peut rien
mesurer à ce moment-là. Remplacée par la récompense décroissante + le témoin, qui agissent
avant/après la session plutôt que pendant.

## Ce que ce squelette ne couvre pas (volontairement)

- Gestion d'erreurs complète, persistence robuste (ici : `UserDefaults` App Group, à migrer
  vers Core Data/SwiftData si besoin).
- Tests unitaires/UI.
- La partie Android (hors périmètre de ce dossier).
