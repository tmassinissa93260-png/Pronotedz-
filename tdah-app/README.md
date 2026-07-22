# Compagnon TDAH — MVP

## Démarrage rapide

1. **Créer un projet Supabase** (gratuit) sur [supabase.com](https://supabase.com), région **Europe (Frankfurt ou Paris)** — important pour l'argument RGPD.
2. Copier `.env.example` en `.env` et remplir avec l'URL et la clé anon du projet (Project Settings → API).
3. Appliquer le schéma dans l'ordre, dans le SQL Editor du dashboard Supabase : `0001_init.sql`, `0002_streak_and_drafts.sql`, `0003_ai_via_pg_net.sql`, `0004_pattern_insights.sql`, `0005_braindump_badges_moments.sql`, `0006_dread_shutdown_ritual.sql`, `0007_routines.sql`, `0008_ordre_tasks.sql`.
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

## Pas encore fait (V2, dans ~2-3 mois une fois qu'on a des utilisateurs actifs)

- Chronothérapie sommeil (la table `wearable_data` existe, l'intégration HealthKit/Health Connect + le coaching restent à faire)
- Détection vocale émotionnelle
- Paiement Stripe (l'app est gratuite pour l'instant, le temps de valider que le produit plaît)

## Sécurité

La clé API Anthropic ne doit **jamais** apparaître dans le code de l'app mobile — elle est stockée dans Supabase Vault et utilisée uniquement à l'intérieur de la fonction Postgres `break_down_task` (SECURITY DEFINER), jamais renvoyée au client. Toutes les tables sont protégées par Row Level Security : chaque utilisateur ne peut lire/écrire que ses propres données.
