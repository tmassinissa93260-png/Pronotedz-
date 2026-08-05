# 11 — APIs externes & dépendances

## 1. APIs externes

### IA — texte & raisonnement

| Fournisseur | Usage | Modèle de prix | Criticité | Repli |
|---|---|---|---|---|
| **Anthropic** | agents créatifs et d'analyse (Sonnet 4.5, Haiku 4.5) | tokens | 🔴 critique | OpenRouter |
| **Groq** | tâches rapides, STT | tokens / heure audio | 🟡 | Anthropic / local |
| **OpenRouter** | filet de secours multi-modèles | tokens + ~5 % | 🟢 | — |
| **Ollama / vLLM** (local) | dernier recours hors ligne | 0 | 🟢 | — |

### IA — image, audio, vision

| Fournisseur | Usage | Prix indicatif | Criticité |
|---|---|---|---|
| **fal.ai** | FLUX schnell/dev — génération d'images | ~0,003 $/img (schnell) | 🔴 critique |
| **Replicate** | repli images, modèles de niche | à la seconde GPU | 🟡 |
| **Groq Whisper large-v3-turbo** | transcription + timings | ~0,04 $/h audio | 🟡 |
| **faster-whisper** (local) | repli STT, hors ligne | 0 | 🟢 |
| **Kokoro-82M** (local) | TTS par défaut | 0 | 🔴 critique |
| **ElevenLabs** | TTS premium (plan Pro) | ~22 €/mois | 🟢 (optionnel v1) |

### Réseaux sociaux

| API | Usage | Point d'attention |
|---|---|---|
| **TikTok Content Posting API** | publication | **Validation d'app obligatoire, plusieurs semaines.** À lancer dès J+1 du projet, c'est le chemin critique de F7 |
| **TikTok Display API** | métriques sur ses propres posts | quotas serrés |
| **Instagram Graph API** (Reels) | publication + insights | requiert compte Business + Page Facebook liée |
| **YouTube Data API v3** | publication Shorts | quota 10 000 unités/jour ; **1 upload ≈ 1 600 unités** → ~6 uploads/jour par projet, à demander en extension |
| **X API v2** | optionnel v2 | tarification volatile |
| **LinkedIn** | optionnel v2 | — |

### Infrastructure & SaaS

| Service | Usage | Coût |
|---|---|---|
| **Cloudflare R2** | artefacts, egress gratuit | ~0,70 €/mois |
| **Cloudflare DNS/WAF/CDN** | edge | 0 € |
| **Hetzner Cloud** | 2 VPS + snapshots | 41,50 €/mois |
| **Stripe** | abonnements, crédits | 1,4 % + 0,25 € |
| **Resend** | emails | 0 € (3 000/mois) |
| **Sentry** | erreurs | 0 € |
| **Supabase Auth** | authentification (option) | 0 € |

## 2. Dépendances logicielles

### Backend Python (3.12)

| Paquet | Rôle | Note |
|---|---|---|
| `fastapi` + `uvicorn[standard]` | API | |
| `pydantic` v2 + `pydantic-settings` | schémas, config | pilier du typage |
| `sqlalchemy` 2.x + `alembic` | ORM, migrations | |
| `asyncpg` | driver PG async | |
| `pgvector` | recherche vectorielle | |
| `arq` | files Redis async | voir [ADR-002](./adr/002-orchestration.md) |
| `redis[hiredis]` | cache, locks, files | |
| `httpx` | client HTTP + retries | |
| `tenacity` | politiques de retry | |
| `anthropic` | SDK officiel | |
| `openai` | couvre Groq/OpenRouter/Ollama/vLLM | compat |
| `fal-client` | images | |
| `boto3` | R2 (S3-compatible) | |
| `jinja2` | rendu de prompts, **sandboxé** | |
| `jsonschema` | validation entrée/sortie d'agents | |
| `scenedetect` | détection de coupes | |
| `librosa` + `soundfile` | BPM, énergie, loudness | |
| `faster-whisper` | STT local | CTranslate2 |
| `Pillow` | manipulation d'images | |
| `langfuse` | traces LLM | |
| `opentelemetry-*` | traces distribuées | |
| `structlog` | logs JSON | |
| `sentry-sdk` | erreurs | |
| `stripe` | paiements | |
| `yt-dlp` | ingestion de vidéos | ⚠️ voir [R1](./12-risques.md#r1) |
| `prometheus-client` | métriques | |

Dev : `pytest`, `pytest-asyncio`, `respx`, `ruff`, `mypy`, `testcontainers`, `locust`.

### Frontend TypeScript

| Paquet | Rôle |
|---|---|
| `next` 15 + `react` 19 | framework |
| `typescript` 5.x | |
| `tailwindcss` + `shadcn/ui` + `radix-ui` | design system |
| `@tanstack/react-query` | état serveur |
| `zustand` | état client |
| `zod` | validation |
| `react-hook-form` | formulaires (gates d'édition) |
| `recharts` | visualisation d'ADN |
| `sonner` | notifications |
| `@vidstack/react` | lecteur vidéo |
| `@sentry/nextjs` | erreurs |
| `playwright` | E2E |

### Binaires système

| Binaire | Rôle | Note |
|---|---|---|
| **ffmpeg 7.x** | montage, encodage | compilé avec `libass`, `libx264`, `libfdk_aac`, `loudnorm` |
| **ffprobe** | analyse média, QA | |
| **fonts** | Inter, Montserrat, Bebas Neue | ⚠️ vérifier les licences pour usage commercial |
| **PostgreSQL 16** + pgvector | base | |
| **Redis 7 / Valkey** | cache & files | |
| **n8n** (Docker) | orchestration | licence *fair-code* — voir R8 |

## 3. APIs internes exposées

`apps/api` — REST versionnée, OpenAPI généré, SDK TS généré.

```
POST   /v1/jobs                        créer un job (Idempotency-Key requis)
GET    /v1/jobs/{id}                   état complet + étapes
GET    /v1/jobs/{id}/stream            SSE — progression temps réel
POST   /v1/jobs/{id}/cancel
POST   /v1/jobs/{id}/resume            reprise manuelle depuis le dernier checkpoint
POST   /v1/jobs/{id}/steps/{key}/retry retry ciblé d'une étape (bypass cache)

GET    /v1/approvals                   inbox des gates en attente
POST   /v1/approvals/{id}/decide       approve | reject | edit

POST   /v1/dna/analyze                 URL ou upload → analyse
GET    /v1/dna/{id}                    ADN + confiances
GET    /v1/dna/templates               bibliothèque, recherche par similarité
POST   /v1/dna/templates/{id}/generate transfert d'ADN vers un nouveau sujet

POST   /v1/assets/upload-url           URL R2 présignée
GET    /v1/renders/{id}/download       URL signée courte

POST   /v1/publications                publier / planifier
GET    /v1/publications/{id}/metrics

GET    /v1/admin/prompts               registry (rôle admin)
POST   /v1/admin/prompts/{id}/promote  canary → stable
POST   /v1/admin/prompts/{id}/rollback
GET    /v1/admin/models                registry de modèles
GET    /v1/admin/costs                 agrégats de coûts

POST   /internal/steps/{agent}/execute appelé par n8n — HMAC + Idempotency-Key
POST   /webhooks/{provider}            stripe, fal, elevenlabs, social
```

**Conventions** : `Idempotency-Key` obligatoire sur tout POST mutant ; erreurs au format
RFC 9457 (`application/problem+json`) ; pagination par curseur ; rate limiting par
`org_id` avec en-têtes `RateLimit-*` ; versionnement par chemin (`/v1`) avec dépréciation
annoncée 90 jours à l'avance.

## 4. Secrets

- Développement : `.env` (jamais commité) + `.env.example` documenté.
- Production : variables d'environnement injectées par Docker Compose depuis un fichier
  `600` root-only. **Pas de Vault en v1** — c'est un choix budgétaire assumé, listé
  comme dette dans [13-evolutions.md](./13-evolutions.md).
- Tokens OAuth des réseaux sociaux : chiffrés en base avec `pgcrypto` (clé dans l'env),
  jamais en clair, jamais dans les logs.
- Rotation : trimestrielle, documentée dans `infra/runbooks/`.
- CI : secrets GitHub Actions, jamais dans le dépôt. Un scan `gitleaks` bloque la CI.
