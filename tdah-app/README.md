# Compagnon TDAH — MVP

## Démarrage rapide

1. **Créer un projet Supabase** (gratuit) sur [supabase.com](https://supabase.com), région **Europe (Frankfurt ou Paris)** — important pour l'argument RGPD.
2. Copier `.env.example` en `.env` et remplir avec l'URL et la clé anon du projet (Project Settings → API).
3. Appliquer le schéma : `supabase db push` (ou coller `supabase/migrations/0001_init.sql` dans le SQL Editor du dashboard Supabase).
4. Déployer la fonction IA :
   ```
   supabase functions deploy ai-task-breakdown
   supabase secrets set ANTHROPIC_API_KEY=sk-ant-...
   ```
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
- Profil : confiance des données (UE, export, suppression), désabonnement en libre-service

## Pas encore fait (V2, dans ~2-3 mois une fois qu'on a des utilisateurs actifs)

- Analyse de patterns long terme (la table `pattern_memory` existe déjà, l'IA d'analyse arrive une fois assez d'historique accumulé)
- Chronothérapie sommeil (la table `wearable_data` existe, l'intégration HealthKit/Health Connect + le coaching restent à faire)
- Brouillon différé pour les messages envoyés en détresse (RSD)
- Détection vocale émotionnelle
- Paiement Stripe (l'app est gratuite pour l'instant, le temps de valider que le produit plaît)

## Sécurité

La clé API Anthropic ne doit **jamais** apparaître dans le code de l'app mobile — elle est uniquement utilisée côté serveur dans la Edge Function `ai-task-breakdown`, configurée via `supabase secrets set`. Toutes les tables sont protégées par Row Level Security : chaque utilisateur ne peut lire/écrire que ses propres données.
