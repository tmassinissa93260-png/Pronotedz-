# Agent IA — réservation coiffeur, commande fast-food, réservation restaurant

Agent d'automatisation basé sur un LLM avec **vraies actions** (tool calling), pas un
chatbot à réponses scriptées : il consulte des disponibilités réelles, crée des
réservations et des commandes en base de données, sur plusieurs canaux.

## Ce qui est inclus

- **Cœur de l'agent** (`src/agent`) : boucle Claude avec tool use (`check_availability`,
  `create_booking`, `cancel_booking`, `check_table_availability`,
  `create_table_reservation`, `cancel_table_reservation`, `create_order`).
- **Base de données** SQLite (`src/db`, `src/businesses/store.ts`) : commerces, services,
  menus, tables, réservations, commandes, historique de conversation par canal/utilisateur.
- **3 commerces de démo** préchargés (`src/businesses/seed.ts`) : un salon de coiffure, un
  fast-food, un restaurant avec réservation de table + vente à emporter/livraison.
- **4 canaux** (`src/channels`) :
  - **Web chat** — fonctionne immédiatement, testable en local (page `public/index.html`).
  - **WhatsApp** — intégration Meta Cloud API complète (webhook + envoi).
  - **Instagram / Messenger** — intégration Meta Messenger Platform complète.
  - **Voix** — intégration Twilio Voice (reconnaissance vocale + réponse parlée gérées par Twilio).

## Ce qui nécessite tes propres comptes

Le code d'intégration WhatsApp, Instagram/Messenger et Voix est complet et prêt à
l'emploi, mais **je ne peux pas le tester en conditions réelles** sans tes identifiants :

| Canal | Compte requis | Où l'obtenir |
|---|---|---|
| WhatsApp | Meta Business + numéro WhatsApp Business | developers.facebook.com |
| Instagram/Messenger | Page Facebook liée à un compte Instagram pro | developers.facebook.com |
| Voix | Compte Twilio + numéro vocal | twilio.com |

Sans ces identifiants, seul le canal **web chat** est utilisable, et seulement si
`ANTHROPIC_API_KEY` est renseigné.

## Démarrage rapide

```bash
npm install
cp .env.example .env
# renseigne au minimum ANTHROPIC_API_KEY dans .env
npm run dev
```

Ouvre `http://localhost:3000`, choisis un commerce dans la liste déroulante et discute
avec l'agent (ex: "je veux un rendez-vous coupe homme demain à 14h, je m'appelle Yanis,
0555112233").

## Brancher un canal externe

1. **WhatsApp** : configure le webhook dans Meta Developer Console vers
   `https://<ton-domaine>/webhooks/whatsapp`, renseigne `WHATSAPP_VERIFY_TOKEN`,
   `WHATSAPP_ACCESS_TOKEN` et `WHATSAPP_BUSINESS_MAP` (associe le `phone_number_id`
   Meta à l'`id` du commerce dans la base).
2. **Instagram/Messenger** : même principe sur `https://<ton-domaine>/webhooks/messenger`
   avec `MESSENGER_VERIFY_TOKEN`, `MESSENGER_PAGE_ACCESS_TOKEN`, `MESSENGER_BUSINESS_MAP`.
3. **Voix** : configure le numéro Twilio pour pointer (méthode POST) vers
   `https://<ton-domaine>/webhooks/voice/incoming`, renseigne `VOICE_BUSINESS_MAP`.

En local, utilise un tunnel (ngrok, Cloudflare Tunnel...) pour exposer le port `3000`
publiquement — ces plateformes exigent une URL HTTPS accessible depuis internet.

## Ajouter un nouveau commerce

Utilise les fonctions de `src/businesses/store.ts` (`createBusiness`, `createService` /
`createMenuItem` / `createTable`) — voir `src/businesses/seed.ts` pour des exemples
concrets pour chacun des 3 types (`hairdresser`, `fastfood`, `restaurant`).

## Sécurité et fiabilité (production)

- **Signature des webhooks** : `META_APP_SECRET` (WhatsApp + Messenger/Instagram) et
  `TWILIO_AUTH_TOKEN` + `PUBLIC_BASE_URL` (voix) sont **obligatoires en production**
  (`NODE_ENV=production`) — sans eux, les webhooks correspondants répondent `503`
  plutôt que d'accepter des requêtes non authentifiées. En développement, l'appel est
  accepté avec un avertissement dans les logs.
- **Anti-rejeu** : chaque message WhatsApp/Messenger porte un identifiant (`message.id`
  / `message.mid`) dédupliqué en base (`processed_events`) — un retry Meta ne
  déclenche pas de double traitement.
- **Idempotence** : la création de réservation/commande est atomique (transaction
  SQLite `EXCLUSIVE` combinant vérification de disponibilité + écriture) et les
  commandes strictement identiques (même client, mêmes articles, même type) faites à
  moins de 2 minutes d'intervalle renvoient la commande existante au lieu d'en créer
  une nouvelle.
- **Autorisation** : `cancel_booking`/`cancel_table_reservation` exigent le numéro de
  téléphone utilisé lors de la création et sont strictement scopés au commerce
  (`business_id`) — impossible d'annuler une réservation d'un autre commerce ou d'un
  autre client.
- **Le LLM ne décide jamais du prix** : le prix vient toujours du menu stocké en base ;
  toute tentative d'injecter un prix/total via l'outil est ignorée. Quantités
  bornées (1 à 50), tous les champs sont revalidés côté serveur avant toute écriture.
- **Rate limiting** : `/api/chat` est limité à 20 requêtes/min/IP.

## Tests

```bash
npm test
```

Suite `node:test` (48 tests) sur base SQLite en mémoire, couvrant : réservation
réussie/en conflit/double appel, annulation avec vérification de propriété,
commande valide/produit inconnu/prix falsifié/quantité invalide, idempotence des
commandes, appels d'outils invalides, signatures webhook Meta/Twilio, verrou de
conversation concurrent, isolation multi-tour et changement de canal, anti-rejeu
webhook. Ce que ces tests **ne couvrent pas** : le comportement réel du LLM (aucune
clé Anthropic dans l'environnement de développement), les appels réels
WhatsApp/Instagram/Twilio (nécessitent de vrais comptes), et les races véritablement
multi-processus (nécessiteraient plusieurs instances du serveur en charge réelle).

## Limites connues (MVP)

- Un seul "créneau/ressource" par commerce pour la coiffure (pas de gestion multi-coiffeur).
- Pas de paiement en ligne intégré (à ajouter si besoin : Stripe, CIB, etc.).
- Pas d'outil `cancel_order` ni de gestion des statuts de commande
  (`preparing`/`ready`/`completed`) côté agent — nécessiterait une interface staff
  dédiée, hors périmètre de cet agent client-facing.
- Pas de modification directe : une modification de rendez-vous/réservation se fait
  via annulation + nouvelle création (l'agent est instruit pour le faire).
- SQLite en fichier local : suffisant pour démarrer. Les transactions `EXCLUSIVE`
  protègent contre les races même multi-processus sur un même fichier, mais pour un
  vrai déploiement multi-serveur il faudra migrer vers Postgres et un rate limiter
  partagé (Redis) plutôt que le limiteur en mémoire actuel.
- Historique de conversation stocké sans limite de taille ni purge automatique — à
  ajouter avant une mise en production à fort volume (TTL, troncature).
