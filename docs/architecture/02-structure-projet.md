# 02 — Structure du projet

Monorepo hybride Python + TypeScript. `uv` (workspaces Python) + `pnpm` (workspaces JS),
orchestrés par `turbo` pour les tâches JS et `just` pour les tâches transverses.

```
pronotedz/
│
├── apps/
│   ├── web/                          # Next.js 15 — App Router, RSC
│   │   ├── app/
│   │   │   ├── (marketing)/          # landing, pricing — statique
│   │   │   ├── (app)/
│   │   │   │   ├── projects/
│   │   │   │   ├── jobs/[id]/        # timeline live du job (SSE)
│   │   │   │   ├── approvals/        # inbox des gates HITL  ← écran critique
│   │   │   │   ├── dna-library/      # bibliothèque d'ADN viraux
│   │   │   │   ├── publishing/
│   │   │   │   └── settings/
│   │   │   └── api/                  # route handlers BFF uniquement
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn/ui
│   │   │   ├── job-timeline/
│   │   │   ├── approval-gate/        # diff, édition inline, approve/reject
│   │   │   ├── dna-visualizer/       # courbes rythme/émotion/énergie
│   │   │   └── video-preview/
│   │   ├── lib/{api-client,sse,auth,store}.ts
│   │   └── e2e/                      # Playwright
│   │
│   ├── api/                          # FastAPI — plan de contrôle
│   │   ├── src/pronotedz_api/
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   │   ├── jobs.py           # POST /v1/jobs, GET /v1/jobs/{id}/stream
│   │   │   │   ├── approvals.py      # gates HITL
│   │   │   │   ├── dna.py            # analyse, bibliothèque, transfert
│   │   │   │   ├── assets.py         # upload direct R2 (URL présignée)
│   │   │   │   ├── publishing.py
│   │   │   │   ├── prompts.py        # admin — registry de prompts
│   │   │   │   ├── models.py         # admin — registry de modèles
│   │   │   │   ├── billing.py        # Stripe + crédits
│   │   │   │   └── webhooks/         # stripe, fal, elevenlabs, n8n, social
│   │   │   ├── middleware/           # authn, tenant(RLS), ratelimit, request_id
│   │   │   ├── services/             # cas d'usage — orchestrent libs/
│   │   │   └── schemas/              # DTO Pydantic (≠ modèles domaine)
│   │   └── tests/
│   │
│   ├── worker/                       # ARQ — exécution des étapes
│   │   ├── src/pronotedz_worker/
│   │   │   ├── queues/{io,media,publish,maintenance}.py
│   │   │   ├── tasks/                # 1 tâche = 1 étape de pipeline
│   │   │   ├── middleware/           # tracing, budget guard, checkpointing
│   │   │   └── settings.py
│   │   └── tests/
│   │
│   ├── renderer/                     # Service de rendu isolé
│   │   ├── src/pronotedz_renderer/
│   │   │   ├── engines/
│   │   │   │   ├── base.py           # interface RenderEngine
│   │   │   │   ├── ffmpeg_engine.py  # v1 — libass + filter_complex
│   │   │   │   └── remotion_engine.py# v2 — derrière la même interface
│   │   │   ├── templates/            # gabarits de montage (.ass, .json)
│   │   │   └── probe.py              # ffprobe, contrôles qualité
│   │   └── tests/fixtures/
│   │
│   └── scheduler/                    # cron interne : timeouts, GC, évals, reconciliation
│
├── libs/                             # Python — cœur réutilisable, sans framework web
│   ├── core/
│   │   ├── domain/                   # entités, value objects, ViralDNA
│   │   ├── pipeline/
│   │   │   ├── engine.py             # moteur durable : steps, checkpoints, reprise
│   │   │   ├── definitions/          # pipelines déclarés en YAML/Python
│   │   │   ├── gates.py              # validation humaine
│   │   │   └── state_machine.py
│   │   ├── errors/                   # taxonomie d'erreurs + politiques
│   │   ├── budget/                   # budget guard, compteurs de coûts
│   │   └── events/                   # bus interne + outbox transactionnel
│   │
│   ├── agents/
│   │   ├── base.py                   # AgentSpec, contrat unique
│   │   ├── registry.py               # découverte + résolution par nom
│   │   ├── analysis/                 # ingest, transcription, scene, vision, audio
│   │   ├── dna/                      # extractor, abstractor, transfer, scorer
│   │   ├── creative/                 # concept, script, hook, storyboard, copy
│   │   ├── production/               # image, voice, music, subtitle, render
│   │   ├── quality/                  # qa, policy, brand-safety
│   │   ├── distribution/             # publisher, scheduler social
│   │   └── meta/                     # supervisor, cost-guardian, feedback
│   │
│   ├── providers/                    # UNIQUE endroit qui connaît les fournisseurs
│   │   ├── registry.py               # lit models.yaml, résout capacité → adapter
│   │   ├── base.py                   # interfaces par capacité
│   │   ├── text/{anthropic,openai,groq,openrouter,ollama}.py
│   │   ├── image/{fal,replicate,openai_images}.py
│   │   ├── audio/{elevenlabs,kokoro,fishaudio}.py
│   │   ├── stt/{groq_whisper,faster_whisper}.py
│   │   └── vision/{anthropic_vision,siglip_local}.py
│   │
│   ├── prompts/
│   │   ├── registry.py               # résolution id@version, canary, rollback
│   │   ├── renderer.py               # Jinja2 sandboxé + validation de sortie
│   │   ├── evals/                    # jeux d'éval + juge LLM
│   │   └── catalog/                  # LE contenu des prompts, versionné en git
│   │       ├── dna/extract_dna@2.1.0.yaml
│   │       ├── creative/write_script@3.0.0.yaml
│   │       └── ...
│   │
│   ├── memory/
│   │   ├── working.py                # contexte du job (Redis, TTL court)
│   │   ├── semantic.py               # pgvector — ADN, hooks, marque
│   │   ├── episodic.py               # historique des runs
│   │   ├── procedural.py             # playbooks appris
│   │   └── compaction.py             # résumé/oubli
│   │
│   ├── cache/
│   │   ├── layers.py                 # L1 process, L2 Redis, L3 R2
│   │   ├── content_address.py        # sha256 canonique des entrées
│   │   ├── semantic_cache.py         # cache LLM par similarité d'embedding
│   │   └── policies.py               # TTL, invalidation par version de prompt/modèle
│   │
│   ├── media/                        # ffmpeg/ffprobe wrappers, ASS, waveform, loudness
│   ├── storage/                      # R2/S3, URLs présignées, cycle de vie
│   ├── db/                           # SQLAlchemy 2, repositories, migrations Alembic
│   └── observability/                # OTel, Langfuse, logs structurés, métriques
│
├── packages/                         # TypeScript partagé
│   ├── sdk/                          # client TS généré depuis l'OpenAPI  ← généré, pas écrit
│   ├── ui/
│   └── tsconfig/ · eslint-config/
│
├── orchestration/
│   └── n8n/
│       ├── workflows/                # JSON exportés, versionnés, 1 fichier = 1 workflow
│       │   ├── WF-01-video-from-idea.json
│       │   └── ...
│       ├── credentials/              # SCHÉMAS uniquement — jamais de secrets
│       ├── lib/                      # snippets JS partagés injectés dans les Code nodes
│       └── scripts/{export,import,lint,diff}.ts   # CI : n8n as code
│
├── infra/
│   ├── docker/                       # Dockerfile par app, multi-stage
│   ├── compose/{dev,prod}.yml
│   ├── traefik/
│   ├── migrations/                   # Alembic
│   ├── seeds/                        # prompts, modèles, plans, templates de rendu
│   └── runbooks/                     # procédures d'incident
│
├── docs/
│   ├── architecture/                 # ce dossier
│   ├── api/openapi.json              # généré
│   └── prompts/                      # doc générée depuis le catalog
│
├── tools/
│   ├── cli/                          # `pdz job run`, `pdz prompt eval`, `pdz dna inspect`
│   └── bench/                        # bench coût/latence par modèle
│
├── .github/workflows/                # lint, test, eval prompts, build, deploy
├── CLAUDE.md                         # conventions pour les agents de code
├── justfile
└── README.md
```

## Notes de conception sur l'arborescence

**`libs/providers` est la seule frontière avec l'extérieur.** Un `grep -r "anthropic"` en
dehors de `libs/providers/` et `infra/seeds/` doit renvoyer zéro résultat. C'est vérifié
par un test d'architecture en CI — sinon le principe P3 se dégrade en trois mois.

**`libs/prompts/catalog` contient des `.yaml`, pas des f-strings.** Le contenu des prompts
est de la donnée. Il est relu, diffé et évalué comme de la donnée.

**`apps/renderer` est un service séparé et pas un module du worker.** Le rendu est
CPU-bound, long, et sujet aux fuites mémoire de ffmpeg ; il doit pouvoir être redémarré,
limité en ressources et scalé indépendamment.

**`packages/sdk` est généré depuis l'OpenAPI de FastAPI.** Zéro dérive de types entre
front et back, zéro DTO recopié à la main.

**`orchestration/n8n/workflows` est versionné en git et diffé en CI.** Un workflow n8n
modifié dans l'UI sans export est un incident de production en puissance ; le script
`diff.ts` échoue la CI si l'instance et le dépôt divergent.
