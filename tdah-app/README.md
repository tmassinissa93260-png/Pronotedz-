# Compagnon TDAH — MVP

## Démarrage rapide

1. **Créer un projet Supabase** (gratuit) sur [supabase.com](https://supabase.com), région **Europe (Frankfurt ou Paris)** — important pour l'argument RGPD.
2. Copier `.env.example` en `.env` et remplir avec l'URL et la clé anon du projet (Project Settings → API).
3. Appliquer le schéma dans l'ordre, dans le SQL Editor du dashboard Supabase : `0001_init.sql`, `0002_streak_and_drafts.sql`, `0003_ai_via_pg_net.sql`, `0004_pattern_insights.sql`, `0005_braindump_badges_moments.sql`, `0006_dread_shutdown_ritual.sql`, `0007_routines.sql`, `0008_ordre_tasks.sql`, `0009_weekly_review.sql`, `0010_weekly_ai_plan.sql`, `0011_priorite.sql`, `0012_icone_manuelle.sql`, `0013_schedule_assistant.sql`.
4. Stocker la clé Anthropic dans Supabase Vault (SQL Editor) :
   ```sql
   select vault.create_secret('sk-ant-...', 'anthropic_api_key');
   ```
   (L'IA tourne côté base de données via `pg_net`, pas via une Edge Function — plus simple à déployer sans terminal.)
5. Installer les dépendances et lancer l'app :
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
- **Palette affinée** (`constants/theme.ts`) : indigo plus vivant en couleur principale, nouvel accent chaud (corail) pour les moments positifs (grenouille du jour, streak), rouge dédié pour la priorité haute — toujours dans la philosophie "calme, peu saturée" d'origine, juste moins plate.
- **Profondeur** : les cartes (tâches, routines, backlog, modes de focus, panneaux coulissants) ont maintenant une ombre douce cohérente plutôt qu'une simple bordure — sensation de relief plus moderne, sans surcharge visuelle.
- **Échelle de rayons unifiée** (`radius.sm/md/lg/xl/pill`) pour des coins de carte, bouton et chip cohérents sur tout l'app.
- Traitement le plus poussé sur les écrans les plus utilisés (Planning, Focus, Backlog, Routines) ; les écrans secondaires (Bilan, Rituel de fin de journée, Respiration, Profil, Auth, Onboarding) héritent automatiquement de la nouvelle police et palette via les tokens partagés, mais n'ont pas encore reçu le traitement ombre/rayon dédié.

## Pas encore fait (V2, dans ~2-3 mois une fois qu'on a des utilisateurs actifs)

- Chronothérapie sommeil (la table `wearable_data` existe, l'intégration HealthKit/Health Connect + le coaching restent à faire)
- Détection vocale émotionnelle
- Paiement Stripe (l'app est gratuite pour l'instant, le temps de valider que le produit plaît)

## Sécurité

La clé API Anthropic ne doit **jamais** apparaître dans le code de l'app mobile — elle est stockée dans Supabase Vault et utilisée uniquement à l'intérieur de la fonction Postgres `break_down_task` (SECURITY DEFINER), jamais renvoyée au client. Toutes les tables sont protégées par Row Level Security : chaque utilisateur ne peut lire/écrire que ses propres données.
