# 10 — Budget 80 €/mois

> ⚠️ **Tous les prix sont des ordres de grandeur à vérifier au moment de l'achat.**
> Les tarifs des fournisseurs IA changent tous les 2–3 mois. Les chiffres servent à
> valider la *structure* du budget et les arbitrages, pas à engager un montant exact.

## 1. Ce que la contrainte élimine

Il faut le dire clairement, parce que ça explique la moitié des choix techniques :

| Écarté | Coût réel | Remplacé par |
|---|---|---|
| n8n Cloud | ~24 €/mois (starter, limité) | n8n auto-hébergé, queue mode |
| Vercel Pro | ~19 €/mois | Next.js en Docker derrière Traefik |
| Supabase Pro | ~23 €/mois | PostgreSQL auto-hébergé (+ Supabase Auth free au début) |
| Remotion Company License | plusieurs centaines €/an | FFmpeg + libass |
| Creatomate / Shotstack | 40–100 €/mois | idem |
| Temporal Cloud | ~90 €/mois | moteur de pipeline maison sur PostgreSQL |
| ElevenLabs Creator | 22 €/mois | Kokoro-82M local (payant réservé au plan premium) |
| Sentry Team | 26 €/mois | Sentry Developer (gratuit) |
| Datadog / Axiom | 30 €+ | Grafana + Loki + Prometheus auto-hébergés |

Total évité : **~275 €/mois**. C'est le prix de l'auto-hébergement, payé en temps
d'exploitation — voir le risque [R7](./12-risques.md#r7).

## 2. Ventilation fixe

| Poste | Détail | €/mois |
|---|---|---|
| **VPS-APP** | Hetzner CX32 — 4 vCPU / 8 Go / 80 Go | 7,50 |
| **VPS-MEDIA** | Hetzner CCX23 — 4 vCPU **dédiés** / 16 Go / 160 Go | 27,00 |
| **Sauvegardes** | snapshots Hetzner (20 % du VPS) | 7,00 |
| **Cloudflare R2** | 50 Go stockés, egress gratuit | 0,70 |
| **Domaine + Cloudflare** | .com amorti + plan Free | 1,30 |
| **Resend** | emails transactionnels, 3 000/mois gratuits | 0,00 |
| **Sentry / Grafana / Loki / Langfuse / n8n / PostgreSQL / Redis** | auto-hébergés ou free tier | 0,00 |
| **Sous-total fixe** | | **43,50** |
| **Crédits IA (variable)** | ce qui reste | **36,50** |
| **TOTAL** | | **80,00** |

## 3. Coût unitaire — vidéo de 30 s, 8 scènes

### Configuration économique (défaut, plan gratuit/starter)

| Étape | Fournisseur | Volume | Coût |
|---|---|---|---|
| Concept | Haiku 4.5 | 1,5 k in / 0,4 k out | 0,0032 € |
| Script + hooks | Sonnet 4.5 (70 % d'entrée en cache) | 3 k in / 1,5 k out | 0,0260 € |
| Storyboard | Haiku 4.5 | 2 k in / 1,2 k out | 0,0073 € |
| Images ×8 | FLUX schnell | 8 | 0,0224 € |
| Voix | Kokoro-82M local | 600 car. | 0,0000 € |
| Musique | banque locale | — | 0,0000 € |
| Sous-titres | libass | — | 0,0000 € |
| Rendu | ffmpeg, ~45 s CPU | — | 0,0000 € |
| QA | Haiku 4.5 vision, 3 frames | — | 0,0060 € |
| Copy plateforme | Haiku 4.5 | — | 0,0025 € |
| Stockage/egress | R2 | ~15 Mo | 0,0002 € |
| **TOTAL** | | | **≈ 0,068 €** |

### Configuration premium (plan Pro)

Sonnet partout + FLUX dev + ElevenLabs Turbo : **≈ 0,42 €** par vidéo.
(Dont ~0,20 € d'images et ~0,09 € de TTS.)

### Analyse d'une vidéo TikTok de 60 s → ADN

| Étape | Coût |
|---|---|
| Téléchargement + normalisation | 0,000 € |
| Transcription (Groq whisper turbo) | 0,0006 € |
| Détection de scènes (PySceneDetect) | 0,000 € |
| Vision, 12 keyframes (Haiku 4.5) | 0,0180 € |
| Features audio (librosa) | 0,000 € |
| Extraction ADN (Sonnet 4.5) | 0,0310 € |
| Abstraction + scoring (Haiku) | 0,0090 € |
| **TOTAL** | **≈ 0,059 €** |

## 4. Capacité mensuelle avec 36,50 € de crédits IA

| Mix | Coût moyen | Vidéos/mois |
|---|---|---|
| 100 % économique | 0,068 € | ~535 |
| 70 % éco / 30 % premium | 0,174 € | ~210 |
| 100 % premium | 0,42 € | ~87 |
| Analyses ADN seules | 0,059 € | ~620 |

**Lecture** : la structure de coût tient. Avec 20 utilisateurs à 10 vidéos/mois en mode
économique (200 vidéos = ~14 €), il reste de la marge. Le point de bascule se situe
vers **500 vidéos/mois** ; au-delà, le budget d'abonnement doit croître avec le chiffre
d'affaires — ce qui est le comportement sain d'un SaaS.

## 5. Garde-fous budgétaires (obligatoires, pas optionnels)

1. **Budget par job** : `jobs.budget_eur` (0,15 € éco / 0,60 € premium). Dépassement → dégradation, puis arrêt.
2. **Budget par org/jour** : token bucket ; dépassement → file basse priorité.
3. **Budget global/jour** : `36,50 / 30 ≈ 1,22 €`. À 100 %, seuls les comptes payants passent.
4. **Coupure dure** à 95 % du budget mensuel : nouveaux jobs refusés avec un message clair.
5. **Alerte P1** sur pic de dépense anormal (voir [09](./09-observabilite.md#7-alertes)).
6. **Plafond de tokens en sortie** sur chaque appel (`max_tokens` toujours explicite).
   Un `max_tokens` absent est le bug le plus cher qui existe sur une API LLM.

## 6. Ordre d'investissement quand le budget augmente

| Budget | Ajout | Pourquoi en premier |
|---|---|---|
| 120 € | 2ᵉ VPS-MEDIA | la latence de rendu est le premier goulot ressenti |
| 150 € | PostgreSQL managé + backups PITR | la perte de données est le seul risque irréversible |
| 200 € | ElevenLabs Creator par défaut | la voix est le facteur de qualité perçue n°1 |
| 300 € | FLUX dev partout + upscaling | qualité visuelle |
| 500 € | Modèles vidéo (Kling/Veo) sur le plan premium | différenciation produit |
| 800 € | Astreinte / infra managée | réduire le risque opérationnel R7 |

## 7. Ce que je surveillerais dès le premier mois

- **Coût réel par vidéo** vs les 0,068 € estimés ici. Un facteur 2 est plausible (retries,
  régénérations, sorties plus longues que prévu) et il faut le détecter en semaine 1.
- **Ratio régénérations / générations**. S'il dépasse 1,5, le coût unitaire réel double
  et c'est un signal produit (les gates arrivent trop tard, ou les prompts sont mauvais).
- **Temps CPU de rendu**. C'est la ressource qui sature avant le budget IA.
