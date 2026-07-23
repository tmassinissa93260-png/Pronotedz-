# Compagnon TDAH — MVP

## Démarrage rapide

1. **Créer un projet Supabase** (gratuit) sur [supabase.com](https://supabase.com), région **Europe (Frankfurt ou Paris)** — important pour l'argument RGPD.
2. Copier `.env.example` en `.env` et remplir avec l'URL et la clé anon du projet (Project Settings → API).
3. Appliquer le schéma dans l'ordre, dans le SQL Editor du dashboard Supabase : `0001_init.sql`, `0002_streak_and_drafts.sql`, `0003_ai_via_pg_net.sql`, `0004_pattern_insights.sql`, `0005_braindump_badges_moments.sql`, `0006_dread_shutdown_ritual.sql`, `0007_routines.sql`, `0008_ordre_tasks.sql`, `0009_weekly_review.sql`, `0010_weekly_ai_plan.sql`, `0011_priorite.sql`, `0012_icone_manuelle.sql`, `0013_schedule_assistant.sql`, `0014_sommeil_humeur.sql`, `0015_stripe_subscriptions.sql`, `0016_ai_usage_limits.sql`, `0017_essai_premium.sql`, `0018_si_alors_energie_ghost_reply.sql`.
4. Stocker la clé Anthropic dans Supabase Vault (SQL Editor) :
   ```sql
   select vault.create_secret('sk-ant-...', 'anthropic_api_key');
   ```
   (L'IA tourne côté base de données via `pg_net`, pas via une Edge Function — plus simple à déployer sans terminal.)
5. Si tu actives l'abonnement (facultatif, rien n'en dépend pour l'instant) : créer un compte [Stripe](https://stripe.com) gratuit, créer un produit avec deux prix récurrents (mensuel, annuel) dans son dashboard, puis dans le SQL Editor :
   ```sql
   select vault.create_secret('sk_test_...', 'stripe_secret_key'); -- clé TEST d'abord, jamais la clé "live" avant d'être prêt à vraiment encaisser
   select vault.create_secret('price_...', 'stripe_price_mensuel');
   select vault.create_secret('price_...', 'stripe_price_annuel');
   ```
6. Installer les dépendances et lancer l'app :
   ```
   npm install
   npm run start
   ```
   Puis scanner le QR code avec l'app **Expo Go** sur ton téléphone (le plus rapide pour tester sans compte développeur Apple/Google au début).

## Ce qui est fait (V1)

- Auth (email/mot de passe) + onboarding (chronotype, profil masking, ton, gamification)
- Planning du jour : ajout de tâches, découpage par IA en sous-étapes, calibration temporelle active (estimation vs réel)
- Focus / body doubling avec IA — mode co-régulation (respiration visuelle continue) et mode responsabilisation
- Dashboard non-déficitaire (autonomie / compétence / connexion, pas de % de complétion)
- Système de streak avec réparations (pas de rupture punitive)
- Check-ins d'interoception (questions fermées, déclenchées par contexte)
- Récompenses à variance (pas le même confetti à chaque fois, pour éviter l'habituation)
- Curseur de granularité pour le découpage de tâches par IA
- Brouillon différé pour les messages envoyés en détresse (RSD)
- Analyse de patterns long terme (`generate_pattern_insight`, se débloque après ~3 semaines d'usage réel)
- Synchronisation d'une tâche vers le calendrier natif du téléphone (icône calendrier sur chaque tâche)
- Regroupement des tâches par moment de journée (N'importe quand / Matin / Jour / Soir), façon Tiimo
- "Vide-tête" : décris toute ta journée en une phrase, l'IA crée directement les tâches structurées avec horaires
- Minuteur de focus avec durée cible (15/25/45 min ou libre) et bouton "+5 min" pendant la session
- Badges à collectionner (premier pas, séries de 7/30 jours, 10 sessions focus, etc.), visibles sur le Dashboard
- Profil : confiance des données (UE, export, suppression), désabonnement en libre-service
- Niveau d'angoisse (1-5, façon "spiciness" de Goblin Tools) par tâche, qui influence la 1ère sous-étape générée par l'IA
- "Mange la grenouille" (Eat the Frog) : bannière qui met en avant la tâche la plus angoissante du jour, avec lancement direct d'une session focus dessus
- Heure de fin prévisible : estimation en temps réel de l'heure à laquelle tu termines si tu enchaînes tes tâches restantes (façon Sunsama)
- Rituel de fin de journée (3 questions courtes : accompli / ce qui bascule à demain / ressenti)
- Narration vocale (TTS) au lancement d'une session focus
- Pause de friction consciente avant d'abandonner une session focus très tôt (façon One Sec) — pas un blocage, juste 5 secondes avant de confirmer
- Timeboxing : lancer une session focus directement sur une tâche précise depuis le planning (bouton ▶️ sur chaque tâche)
- Routines récurrentes (façon Tiimo) : modèles de tâches qui se reproduisent automatiquement les jours choisis, gérables sur un écran dédié (créer, mettre en pause, supprimer)
- Vue frise horaire (façon Tiimo) en alternative à la liste : tâches positionnées visuellement sur une timeline colorée par moment de journée, basculable via le bouton "Frise"/"Liste"
- Historique en heatmap (façon GitHub contributions) sur le Dashboard, 12 dernières semaines — volontairement sans case "rouge" pour un jour manqué, cohérent avec le système de streak à réparation
- Report non-punitif d'une tâche à demain (façon "Too Hard Right Now" de Focus One) : icône dédiée sur chaque tâche + report groupé sur l'écran fin de journée — répond à la plainte la plus citée dans les avis Tiimo/Sunsama sur la gestion des tâches non finies
- Réorganisation manuelle des tâches (flèches haut/bas dans chaque section) — répond à une plainte récurrente sur Tiimo App Store sur l'impossibilité de déplacer une tâche une fois ajoutée
- Détection des trous dans la journée sur la vue frise (créneaux libres ≥ 30 min affichés en pointillés) — répond à une demande citée dans les avis Tiimo sur l'absence de représentation visuelle des créneaux libres
- Focus à deux (façon Focusmate) : body doubling avec une vraie personne, pas juste l'IA — créer une session génère un code à partager, l'autre le rejoint, minuteur partagé + boutons d'encouragement en temps réel via Supabase Realtime (presence + broadcast, sans table dédiée). Pas de vidéo/audio (demanderait un SDK natif + un build EAS), mais la présence mutuelle engagée est le vrai moteur de Focusmate, pas la qualité vidéo
- Icône colorée par tâche (façon Tiimo) : devinée à partir de mots-clés dans le titre (📞 appel, 💊 médicament, 🍽️ repas, 🛒 courses...), aucune saisie manuelle requise
- Sections repliables/dépliables dans le planning (chevron sur "MATIN", "JOUR", "SOIR"...)
- Badge de série visible directement sur l'écran principal du planning (pas seulement sur le Bilan)
- Sélecteur de jour en semaine (L M M J V S D avec dates, navigation semaine précédente/suivante) — permet de préparer demain ou revoir hier, plus seulement "aujourd'hui"
- Anneau de progression circulaire animé autour du minuteur de focus (façon Tiimo), plus lisible d'un coup d'œil qu'un simple décompte
- Pause/reprise pendant une session focus (bouton ⏸/▶️ à côté de "+5 min")
- Rappels locaux 5 min avant l'heure d'une tâche (notifications programmées sur l'appareil, sans push distant — ça marche encore dans Expo Go) + réglage manuel de l'heure d'une tâche pour en profiter même sans passer par le Vide-tête
- Bilan hebdomadaire réflexif (3 questions : ce qui a marché / ce qui a été dur / la priorité de la semaine prochaine), accessible depuis le Dashboard, en plus du rituel quotidien
- Respiration guidée (façon RespiRelax) accessible à tout moment depuis le planning, pas seulement pendant une session focus — respiration carrée (4-4-4-4) avec durée 1/3/5 min ou libre
- Rappel de relance douce ~10 min après l'heure prévue d'une tâche si elle n'est toujours pas faite, en plus du rappel 5 min avant — volontairement pas un rappel qui insiste en boucle (façon TickTick), pour rester cohérent avec le principe "discrète et non intrusive"

### Fonctionnalités "hyper avancées" (au-delà de ce que Tiimo propose)

- **Coach IA proactif** : quand une tâche marquée très angoissante (4-5/5) est programmée à un moment de journée où l'historique montre un faible taux de réussite (échantillon ≥ 3, écart ≥ 20 points avec un autre moment), une bannière propose de la déplacer en un tap. Pas d'appel IA — juste une agrégation de l'historique des tâches, rapide et gratuit.
- **Plan de semaine complet par IA** : le Vide-tête a maintenant un bascule "Aujourd'hui" / "Toute la semaine" — décrire toute sa semaine en vrac fait répartir les tâches sur les 7 jours par l'IA (`plan_week_from_braindump`), au lieu de tout entasser sur un seul jour.
- **Matching automatique pour le Focus à deux** : en plus de créer une session et partager un code, un bouton "Trouver un binôme maintenant" met en relation avec un inconnu de l'app disponible au même moment, via une salle d'attente Supabase Realtime (élection déterministe, pas de table dédiée). Tiimo ne propose que du body doubling simulé par IA, jamais un vrai humain.

### Suite à la recherche approfondie TDAH (science + témoignages + marché français)

Trois recherches menées en parallèle : bases physiologiques/scientifiques du TDAH et approches non-médicamenteuses, impact relationnel (couple/famille) et professionnel avec témoignages réels, et marché/communauté TDAH française face à Tiimo. Premier lot de fonctionnalités qui en découle (aucune ne demande de nouvelle dépendance ni de migration SQL) :

- **"Juste 5 secondes"** (`app/(tabs)/focus.tsx`) : bouton à friction quasi nulle qui démarre une session directement, sans choix de mode ni de durée — hack psychologique documenté contre la paralysie de démarrage (le vrai obstacle TDAH n'est pas de faire la tâche, c'est de la commencer).
- **Mouvement autorisé pendant le focus** : mention explicite pendant une session ("bouger, gigoter, te lever si besoin") — la recherche scientifique montre que le fidgeting spontané est corrélé à un meilleur maintien de l'attention chez les profils TDAH (régulation de l'éveil cortical), jamais une distraction à réprimer.
- **Roulette des tâches** ("Choisis pour moi" dans le menu Outils) : tire au sort une tâche du jour non terminée — supprime la fatigue décisionnelle face à une liste, avec possibilité de retirer et retirer jusqu'à en accepter une.
- **Suggestion "marge de sécurité TDAH"** sur l'estimation d'une tâche : suggestion visible et tapable (×1.4, jamais imposée silencieusement) plutôt qu'une multiplication automatique qui aurait faussé la calibration estimé/réel déjà en place.
- **Amnistie générale** (menu Outils) : remet d'un coup toutes les tâches en retard à aujourd'hui, sans compteur d'échec ni notification culpabilisante — étend la logique déjà en place pour le report d'une tâche individuelle à un geste global.
- **Mode Crash** (menu Outils) : pour les moments de surcharge où choisir quoi faire est lui-même un obstacle — annule les rappels du jour, reporte tout à demain sauf la tâche la moins angoissante (facultative même dans ce cas), avec accès direct à la respiration guidée avant de confirmer.
- **Maintenance prédictive nocturne** : signal doux (jamais bloquant, une seule fois par nuit) quand beaucoup de tâches sont ajoutées d'un coup après minuit — signe possible d'hyperfocus nocturne, sans jamais empêcher d'ajouter quoi que ce soit.

Deuxième lot, qui demande une migration (`0018_si_alors_energie_ghost_reply.sql` : colonnes `tasks.si_alors`/`tasks.cout_energie`, fonction IA `generate_ghost_reply`) :

- **Plans "si...alors..."** (implementation intentions, `tasks.si_alors`) : champ optionnel par tâche, ajoutable/modifiable d'un tap — preuve scientifique solide (Gawrilow & Gollwitzer et suivants) que ce type de plan transfère le contrôle de l'action vers un déclencheur environnemental plutôt que de compter sur la volonté seule, contournant le déficit exécutif au lieu de le combattre.
- **Batterie mentale** (`tasks.cout_energie`, `faible`/`moyen`/`eleve`) : coût en énergie par tâche indépendant de sa durée, cyclable d'un tap (icône éclair à côté du drapeau de priorité). Une jauge (`🔋 XX%`) apparaît dans l'en-tête dès qu'une tâche du jour en a un — budget arbitraire de 10 points/jour, juste un signal relatif. Verrouillage doux (jamais bloquant) : lancer le focus sur une tâche coûteuse quand la batterie est basse déclenche une confirmation, jamais un blocage.
- **Générateur de réponses aux messages fantômes** (menu Outils, `lib/ai/ghostReply.ts`, fonction SQL `generate_ghost_reply`, même schéma pg_net que `interpret_schedule_command`) : décrire un message resté sans réponse trop longtemps par évitement/anxiété fait générer un brouillon court par l'IA — jamais envoyé automatiquement, copiable en un tap (`expo-clipboard`).
- **Rétention par le pardon** (`streaks.derniere_activite`, déjà en base depuis la logique de streak) : après 4 jours ou plus sans activité, un message chaleureux unique par ouverture ("Content de te revoir") propose de tout ramener à aujourd'hui plutôt que d'afficher un compteur cassé ou une notification culpabilisante.
- **Rappel lumière du matin** (`lib/notifications.ts`, écran Sommeil) : notification locale quotidienne programmée ~15 min après l'heure de lever renseignée — la lumière matinale est le levier le mieux documenté pour avancer une horloge biologique en retard de phase, très fréquent en TDAH (jusqu'à 75% des adultes selon la littérature sur les rythmes circadiens), en complément direct de la chronothérapie sommeil déjà en place.
- **Bruit blanc/rose pendant le focus** (`expo-audio`, `assets/sounds/bruit-blanc.wav` et `bruit-rose.wav`) : deux boucles de 8 secondes générées localement (aucun service tiers, script Node one-shot — pas d'assets téléchargés), fondu aux extrémités pour un raccord inaudible même sur 45 min. Preuve modérée mais spécifique au TDAH (modèle de l'hypo-éveil : le son compense un sous-éveil cortical, effet neutre voire délétère chez les profils sans TDAH). Coupé automatiquement à la fin de la session, quel que soit le chemin de sortie.

### Suite à l'analyse de 15 captures d'écran Tiimo (App Store + site)

- **Niveau de priorité** (Haute/Moyenne/Basse, `niveau_priorite`) distinct du niveau d'angoisse — un drapeau à côté du titre, tap pour faire défiler les niveaux
- **"Je suis en retard ?"** : décale d'un coup toutes les tâches restantes du jour ayant une heure fixée (+5/10/15/30 min), capture le même besoin que le chat IA de Tiimo ("move all my tasks by 10min") sans dépendre d'un appel IA
- **Sous-tâches visibles et cochables pendant la session focus** (auparavant seulement dans la liste du planning) — répond directement à une capture Tiimo montrant sa checklist affichée sous le minuteur
- **Icône et couleur personnalisables manuellement par tâche** (façon "3000+ couleurs et icônes" de Tiimo) : tap sur la bulle d'icône d'une tâche pour choisir parmi une sélection curatée, avec un retour à l'auto-détection possible à tout moment
- **Assistant conversationnel de planning** (façon le chat IA de Tiimo qui exécute des commandes) : "je suis en retard, décale tout de 15 min", "reporte le ménage à demain", "mets les courses en priorité haute", ou une phrase vague comme "tout me semble urgent" — l'IA classe le message dans une action fixe et déterministe (jamais elle n'écrit directement en base), et c'est le client qui exécute la mutation réelle
- **Backlog "à placer"** (équivalent du glisser-déposer calendrier de Tiimo, en version tap) : les tâches du jour sans horaire, groupées par priorité, avec un bouton "Maintenant" pour un placement en un tap ou un champ heure pour choisir précisément — un vrai geste de glisser-déposer ne peut pas être testé de façon fiable dans cet environnement (aucun appareil tactile réel disponible), donc pas de dépendance ajoutée pour du code non vérifiable
- Note : la saisie vocale façon co-planner Tiimo reste bloquée en l'état — elle nécessite un module natif de reconnaissance vocale (`expo-speech-recognition`) incompatible avec Expo Go, donc un build EAS personnalisé serait requis

### Refonte visuelle

- **Typographie Manrope** (`@expo-google-fonts/manrope`) sur tout l'app à la place de la police système — géométrique, terminaisons arrondies, cohérente avec le ton bienveillant du produit. Chargée au démarrage (`app/_layout.tsx`), un court écran de chargement s'affiche le temps que les graisses (400 à 800) soient prêtes.
- **Pairing serif/sans sur le titre d'écran** (`@expo-google-fonts/fraunces`, `typography.title` dans `constants/theme.ts`) : Fraunces en semibold remplace Manrope uniquement sur le grand titre de chaque écran principal ("Aujourd'hui", "Focus", "Profil"...) — un seul point d'usage par écran, comme chez Tiimo, pour donner un effet "designé" sans diluer l'identité. Tout le reste (corps de texte, boutons, étiquettes) reste en Manrope.
- **Palette affinée** (`constants/theme.ts`) : indigo plus vivant en couleur principale, nouvel accent chaud (corail) pour les moments positifs (grenouille du jour, streak), rouge dédié pour la priorité haute — toujours dans la philosophie "calme, peu saturée" d'origine, juste moins plate.
- **Profondeur** : les cartes (tâches, routines, backlog, modes de focus, panneaux coulissants) ont maintenant une ombre douce cohérente plutôt qu'une simple bordure — sensation de relief plus moderne, sans surcharge visuelle.
- **Échelle de rayons unifiée** (`radius.sm/md/lg/xl/pill`) pour des coins de carte, bouton et chip cohérents sur tout l'app.
- Traitement le plus poussé sur les écrans les plus utilisés (Planning, Focus, Backlog, Routines) ; les écrans secondaires (Bilan, Rituel de fin de journée, Respiration, Profil, Auth, Onboarding) héritent automatiquement de la nouvelle police et palette via les tokens partagés, mais n'ont pas encore reçu le traitement ombre/rayon dédié.

### Redesign "focus-first" et palette sobre/premium

Deuxième passe de refonte, en deux temps.

**Approche focus-first** (hiérarchie, capture, feedback, mode focus, navigation) :
- **Capture rapide globale** (`components/QuickCaptureFab.tsx`) : bouton flottant présent sur tout l'app (sauf pendant une session de focus active), texte libre sans champ obligatoire, la note atterrit directement dans le backlog du jour. Remplace l'ancien champ "Ajouter une tâche" de l'écran du jour, devenu redondant.
- **Dark mode par défaut** (`lib/theme/ThemeProvider.tsx`) — le sélecteur Système/Clair/Sombre reste disponible dans Profil.
- **Retour haptique optionnel** sur chaque complétion de tâche/sous-tâche (`expo-haptics`, branché dans `RewardProvider.celebrate()`), désactivable dans Profil.
- **Mode focus renforcé** : notifications coupées automatiquement pendant une session (`lib/notifications.ts`, `setNotificationsSuspended`), transition en fondu à l'entrée/sortie de session (`Animated.Value` dans `focus.tsx`).
- **Densité réduite** sur les cartes de tâche : actions secondaires (calendrier, report) regroupées dans un menu "..." plutôt qu'affichées en permanence.
- **Zones cliquables** revues sur les écrans les plus utilisés pour viser 44px minimum (chips, boutons d'icônes).

**Palette "sobre et premium vert"** (`constants/theme.ts`), suite à un retour direct sur la V1 (jugée trop "2018") et en s'inspirant du ton sobre de FocusFirst (App Store) :
- Fond noir neutre profond en mode sombre (plus de teinte bleu-nuit/indigo, qui lisait comme un gabarit SaaS générique) ; fond clair recalibré vers un blanc légèrement vert-gris en cohérence.
- Vert unique comme couleur de marque (primaire ET succès) — choisi assez soutenu (`#059669` sombre / `#15803D` clair) pour rester lisible en texte blanc sur fond plein, pas juste "joli" en grande surface claire.
- Ombres neutres (noir pur) au lieu de la teinte violette précédente.
- Rayons de carte légèrement agrandis (`radius.md/lg/xl`) pour des cartes plus aérées.
- **Abandon du pairing serif/sans** : Fraunces retiré (police et dépendance `@expo-google-fonts/fraunces` supprimées) — le titre d'écran passe en Manrope ExtraBold. Le duo serif/grotesque lisait plus "édito" que "outil premium" ; la hiérarchie vient maintenant du poids et de la taille, pas du changement de famille.

### Ajustements suite à une recherche sur le design et le TDAH

Après la refonte visuelle ci-dessus, recherche ciblée sur la littérature UX/accessibilité cognitive pour vérifier (et corriger) les choix faits :

- **Espacement > forme des lettres** : la lecture chez les personnes TDAH est plus affectée par un texte dense/resserré que par la police choisie elle-même. Conséquence concrète : le `letterSpacing: -0.4` "façon logo" sur le titre a été retiré (remplacé par un espacement légèrement positif), et un `lineHeight` généreux (~1.4-1.5x la taille de police) a été ajouté à tous les styles de texte de base (`title`/`heading`/`body`/`caption`) — c'était resserré par défaut avant cette recherche.
- **Saturation ambiante à éviter** : la littérature associe la haute saturation à une charge attentionnelle plus lourde (dans la lignée des interventions "écran en niveaux de gris" étudiées pour réduire l'usage compulsif du téléphone). L'accent corail (utilisé sur la bannière "grenouille" et le badge de série) est passé de 100% à ~78% de saturation — toujours chaleureux, moins criard. Le reste de la palette (fond, surfaces) était déjà à faible saturation.
- **Mouvement respecté selon les préférences système** : le toast de récompense (`RewardProvider`) interroge maintenant `AccessibilityInfo.isReduceMotionEnabled()` — si l'utilisateur a activé "Réduire les animations" dans les réglages de son téléphone, le fade s'efface au profit d'un affichage direct, conformément à la recommandation WCAG 2.3.3 sur les animations non essentielles (le mouvement, même discret, peut capter l'attention de façon disproportionnée chez les personnes TDAH).
- **Sans-serif géométrique confirmé pour tout ce qui se lit** : Manrope reste dans la même famille que les polices recommandées pour le TDAH/la dyslexie (Century Gothic, Trebuchet, Open Sans — sans-serif, formes de lettres nettes, pas d'italique utilisé dans l'app) sur tout le texte fonctionnel (corps, boutons, étiquettes). La réserve documentée ci-dessus (`typography.title`) est un cas différent : un grand titre de 3-4 mots par écran se reconnaît d'un coup d'œil plutôt que se lit lettre à lettre — la recherche sur la lisibilité en contexte TDAH porte sur le texte dense, pas ce genre d'usage ponctuel.
### Mode focus

- Nouveau réglage (Profil → Apparence → **Mode focus**) qui va plus loin que le mode sombre/clair : neutralise les touches de couleur purement décoratives (bannière "grenouille", badge de série, bulle d'icône de tâche — jusqu'à une dizaine de teintes pastel différentes affichées en même temps dans une liste) en les remplaçant par les tokens neutres déjà existants (`textMuted`/`surfaceAlt`). Les couleurs fonctionnelles (drapeau de priorité, flammes d'angoisse, boutons) restent intactes — elles portent une information, pas juste de la décoration.
- Coupe aussi les animations non essentielles : le cercle de respiration en mode co-régulation du Focus reste fixe au lieu de pulser en boucle, et le toast de récompense s'affiche directement sans fondu (même logique que le respect du réglage système "Réduire les animations", mais activable indépendamment).
- Réglage persistant sur l'appareil (`AsyncStorage`), indépendant du choix clair/sombre — les deux se combinent.

### Mode sombre

- **Deux palettes complètes** (`lightColors`/`darkColors` dans `constants/theme.ts`) — le mode sombre n'est pas un simple assombrissement automatique : fond noir bleu nuit (`#0A0D16`, jamais noir pur, pour limiter l'éblouissement en faible luminosité), volontairement différent du noir plat de Tiimo — l'indigo de la marque, légèrement rafraîchi vers le bleu, garde du relief entre fond/cartes/bordures là où leur écran perd toute hiérarchie visuelle. Couleurs vives éclaircies individuellement pour rester lisibles sur fond sombre.
- **`lib/theme/ThemeProvider.tsx`** : détecte la préférence système (`useColorScheme`) par défaut, avec une préférence manuelle (Système/Clair/Sombre) mémorisée sur l'appareil (`AsyncStorage`) — réglable depuis Profil → Apparence. `app.json` est passé de `userInterfaceStyle: "light"` (forcé) à `"automatic"`.
- Chaque écran lit désormais ses couleurs via `useTheme()` plutôt que d'importer `colors` en statique, avec les styles construits par une fonction `makeStyles(colors)` appelée à chaque changement de thème (nécessaire en React Native : un `StyleSheet.create` figé au chargement du module ne peut pas se mettre à jour tout seul).
- Traitement complet sur les écrans à plus fort trafic (Planning, Focus, Backlog, Routines, Profil) + les composants qu'ils utilisent (minuteur circulaire, frise horaire, check-in d'interoception, toast de récompense) et la coque de navigation (onglets, en-têtes natifs Backlog/Routines). Les écrans restants (Bilan, Rituel de fin de journée, Respiration, Brouillon différé, Auth, Onboarding) n'ont pas encore été convertis — ils restent figés en palette claire quel que soit le thème choisi, en attendant leur conversion.

### Chronothérapie sommeil (saisie manuelle)

- Nouvel écran **Sommeil** (dans le menu Outils) : saisie manuelle de l'heure de coucher/lever et d'une note de qualité ressentie (1-5), historique des nuits récentes.
- **Corrélation sommeil/productivité** (`getSleepTaskCorrelation`, agrégation pure côté client, pas d'appel IA — même logique que le coach proactif) : compare le taux de tâches terminées les jours qui suivent une bonne nuit (≥7h ou qualité ≥4) contre les jours qui suivent une nuit courte ou difficile, affiché en bannière dès qu'il y a assez de données (≥3 nuits de chaque côté).
- La synchro automatique Apple Watch/Health Connect reste bloquée par Expo Go (module natif, demanderait un build EAS) — même limitation que la saisie vocale. La table `wearable_data` a une colonne `source` déjà prête à recevoir `apple_watch`/`oura`/`whoop` le jour où ce build existe, sans migration supplémentaire.

### Check-in "humeur"

- Remplace la détection vocale émotionnelle prévue en V2 : analyser le ton de la voix demanderait un micro natif (bloqué dans Expo Go) et un modèle d'émotion externe non défini — une question fermée sur l'humeur ressentie (`😔 Dur` / `😐 Neutre` / `🙂 Bien`) capture l'essentiel du signal utile sans dépendre de rien de natif, intégrée au même système de check-in d'interoception existant.

### Infrastructure d'abonnement (Stripe)

- **Stripe Checkout** (page hébergée, ouverte dans le navigateur via `expo-web-browser`) plutôt que le SDK natif `@stripe/stripe-react-native`, qui casserait Expo Go.
- **Aucun webhook** : confirmer un paiement nécessiterait normalement un point d'entrée HTTP public, hors du pattern pg_net sortant utilisé partout ailleurs dans ce projet. À la place : `confirm_checkout_session` vérifie activement auprès de Stripe juste après le retour dans l'app (lien `tdahapp://checkout-retour`), et `refresh_subscription_status` revérifie à chaque ouverture de l'écran Profil — capte les renouvellements/annulations avec un léger différé plutôt qu'en temps réel.
- Nouvel écran **Profil → Abonnement → Voir les offres**, plans mensuel/annuel.

### Stratégie gratuit/payant

Recherche sur les benchmarks freemium 2026 (RevenueCat, ChartMogul) et sur le modèle réel de Tiimo (notre concurrent direct le plus établi aux USA) avant de trancher — et alignement volontaire sur ce modèle plutôt qu'une répartition plus agressive testée puis abandonnée :

- **Le piège documenté à éviter** : un tier gratuit trop vide tue la conversion (personne ne reste assez longtemps pour découvrir la valeur), et verrouiller totalement une fonctionnalité qu'on a déjà goûtée se retourne contre le produit (cas cité : un concurrent a verrouillé son filtre le plus populaire → vague de 1 étoile et désinstalls en quelques heures). Tiimo lui-même garde son IA (générateur de sous-tâches, Co-Planner) **accessible en gratuit mais limitée**, jamais bloquée d'un coup — et réserve à Pro : sync calendrier, multi-appareils, personnalisation, IA illimitée. Les mécaniques de base du planificateur (routines, backlog) restent gratuites chez eux.
- **Répartition retenue** — gratuit et illimité : planning quotidien (priorité, angoisse, moment de journée), vues liste/frise, minuteur focus solo, streak/badges/récompenses, check-ins, rappels locaux, **mode sombre et mode focus** (verrouiller de l'accessibilité sur une app pensée pour le TDAH contredirait la mission), découpage IA d'une tâche (le "aha moment"), report/réorganisation, Coach IA proactif (zéro coût, agrégation locale), **Routines et Backlog** (mécaniques de base du planificateur, comme chez Tiimo). Gratuit mais **limité** (3 usages IA gratuits par mois, mutualisés — compteur toujours visible) : Vide-tête, Assistant conversationnel, Analyse de patterns long terme — jamais bloqués d'un coup, juste comptés. Premium (usage IA illimité en prime) : personnalisation icône/couleur, synchronisation calendrier — ce sont les fonctionnalités que Tiimo réserve aussi à son Pro. Restent premium comme différenciateurs propres à l'app (sans équivalent chez Tiimo) : Focus à deux, Bilan hebdomadaire réflexif, suivi du sommeil.
- **Mise en place — verrouillage total** (`lib/billing/stripe.ts`) : `usePremiumGate()` expose `gate(label, action)` — exécute l'action si l'abonnement (ou l'essai) est actif, sinon affiche une alerte au ton cohérent avec le reste de l'app (jamais culpabilisante) puis propose `/paiement`. Utilisé pour la personnalisation icône/couleur, la synchronisation calendrier, Focus à deux, Sommeil, Bilan hebdomadaire.
- **Mise en place — quota IA mensuel** (`lib/billing/aiQuota.ts`, migration `0016_ai_usage_limits.sql`) : `ai_usage` (table `user_id` + `mois` 'AAAA-MM' + `compteur`) suit l'usage par utilisateur, incrémenté via la fonction `SECURITY DEFINER` `record_ai_usage`. `useAiQuota()` expose `remaining`/`canUse`/`recordUsage()` ; chaque écran appelle son propre `requireAi(label, action)` (même ton non-culpabilisant que `gate()`) avant Vide-tête, Assistant et Analyse de patterns, et appelle `recordUsage()` juste après un appel IA réussi. Usage illimité et compteur ignoré pour les abonnés premium.
- **`<PremiumScreen label="...">`** (`components/PremiumScreen.tsx`) enveloppe les écrans premium à verrouillage total restants (Sommeil, Bilan hebdomadaire) en filet de sécurité si quelqu'un y accède directement par lien profond plutôt que par un bouton déjà verrouillé. Backlog et Routines ne l'utilisent plus, ces écrans sont pleinement gratuits.

#### Pousser à l'abonnement sans que ça se sente (essai, nudges, présentation)

Objectif explicit du produit : une vraie pression de conversion, mais qui ne se vit jamais comme du forcing — cohérent avec le principe déjà établi de ne jamais culpabiliser.

- **Essai premium de 7 jours, sans carte bancaire** (migration `0017_essai_premium.sql`, colonne `profiles.essai_premium_fin`) : tout est débloqué dès l'inscription, aucune friction de paiement au départ. `useSubscription()` calcule `isPremium` comme `abonnement actif OU essai en cours` — la limite ne se fait sentir qu'à la fin de l'essai (aversion à la perte, mieux documentée pour convertir qu'un mur de vente immédiat). `isEssaiActif` et `essaiJoursRestants` pilotent l'affichage du décompte dans Profil et sur `/paiement`.
- **Nudges au bon moment, pas au moment du blocage** : sur l'écran d'accueil, une bannière discrète et non-bloquante (dismissible, jamais un `Alert`) apparaît quand le streak franchit un palier (3, 7, 14, 30, 60, 100 jours) pour les non-abonnés (gratuit ou en essai) — proposer l'abonnement pendant une lancée plutôt que juste après avoir buté sur une limite.
- **Présentation plus douce du verrouillage** : les icônes 🔒 (cadenas, connotation négative/blocage) ont été remplacées par des puces "✨ Premium" dans le menu Outils et sur Focus à deux — même information, cadrage aspirationnel plutôt que punitif.
- **Limite connue** : la vérification est côté client uniquement pour l'instant — les fonctions SQL des fonctionnalités IA ne vérifient pas encore l'abonnement, l'essai ni le quota elles-mêmes. Suffisant pour une V1 sans utilisateurs adverses, mais une vraie protection des revenus demandera d'ajouter ce contrôle aussi côté serveur (voir "Pas encore fait" ci-dessous).

## Pas encore fait (V2, dans ~2-3 mois une fois qu'on a des utilisateurs actifs)

- Vérification de l'abonnement et du quota IA côté serveur (pas seulement client) dans les fonctions SQL des fonctionnalités premium — actuellement, un appel direct à l'API contournerait le verrouillage
- Stratégie marketing / contenu TikTok (le split gratuit/payant ci-dessus est la base sur laquelle s'appuyer)

- Synchronisation automatique du sommeil (Apple Watch/Health Connect) — nécessite un build EAS, voir ci-dessus
- Passage en clé Stripe "live" (le code tourne en clé de test tant que ce n'est pas fait explicitement)

## Sécurité

La clé API Anthropic ne doit **jamais** apparaître dans le code de l'app mobile — elle est stockée dans Supabase Vault et utilisée uniquement à l'intérieur de la fonction Postgres `break_down_task` (SECURITY DEFINER), jamais renvoyée au client. Toutes les tables sont protégées par Row Level Security : chaque utilisateur ne peut lire/écrire que ses propres données.
