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

## Limites connues (MVP)

- Un seul "créneau/ressource" par commerce pour la coiffure (pas de gestion multi-coiffeur).
- Pas de paiement en ligne intégré (à ajouter si besoin : Stripe, CIB, etc.).
- Pas d'authentification sur les endpoints webhook au-delà de la vérification Meta —
  à durcir avant une mise en production (validation de signature `X-Hub-Signature-256`
  pour WhatsApp/Messenger, validation de signature Twilio pour la voix).
- SQLite en fichier local : suffisant pour démarrer, à migrer vers Postgres pour un usage
  multi-serveur/production.
