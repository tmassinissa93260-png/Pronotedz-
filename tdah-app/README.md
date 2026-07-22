# Compagnon TDAH — MVP

## Démarrage rapide

1. **Créer un projet Supabase** (gratuit) sur [supabase.com](https://supabase.com), région **Europe (Frankfurt ou Paris)** — important pour l'argument RGPD.
2. Copier `.env.example` en `.env` et remplir avec l'URL et la clé anon du projet (Project Settings → API).
3. Appliquer le schéma dans l'ordre, dans le SQL Editor du dashboard Supabase : `0001_init.sql`, `0002_streak_and_drafts.sql`, `0003_ai_via_pg_net.sql`, `0004_pattern_insights.sql`.
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
- Profil : confiance des données (UE, export, suppression), désabonnement en libre-service

## Pas encore fait (V2, dans ~2-3 mois une fois qu'on a des utilisateurs actifs)

- Chronothérapie sommeil (la table `wearable_data` existe, l'intégration HealthKit/Health Connect + le coaching restent à faire)
- Détection vocale émotionnelle
- Paiement Stripe (l'app est gratuite pour l'instant, le temps de valider que le produit plaît)

## Sécurité

La clé API Anthropic ne doit **jamais** apparaître dans le code de l'app mobile — elle est stockée dans Supabase Vault et utilisée uniquement à l'intérieur de la fonction Postgres `break_down_task` (SECURITY DEFINER), jamais renvoyée au client. Toutes les tables sont protégées par Row Level Security : chaque utilisateur ne peut lire/écrire que ses propres données.
