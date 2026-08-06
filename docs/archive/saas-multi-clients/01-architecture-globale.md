# 01 — Architecture globale

## 1. Vue d'ensemble (C4 niveau 2 — conteneurs)

```mermaid
flowchart TB
    subgraph client["Client"]
        WEB["Next.js 15<br/>Dashboard + Gates HITL"]
    end

    subgraph edge["Edge"]
        CF["Cloudflare<br/>DNS · WAF · CDN"]
    end

    subgraph core["Plan de contrôle — VPS App"]
        API["FastAPI<br/>REST + SSE + Webhooks"]
        SCHED["Scheduler<br/>cron · timeouts · GC"]
        N8N["n8n queue-mode<br/>intégrations · métier"]
    end

    subgraph compute["Plan d'exécution"]
        WIO["Workers I/O<br/>ARQ · concurrency 50<br/>agents LLM/API"]
        WCPU["Workers Média<br/>ffmpeg · whisper<br/>concurrency 2"]
    end

    subgraph state["Plan de données"]
        PG[("PostgreSQL 16<br/>+ pgvector<br/>SOURCE DE VÉRITÉ")]
        RD[("Redis / Valkey<br/>queues · cache L2 · locks")]
        R2[("Cloudflare R2<br/>artefacts adressés<br/>par contenu")]
    end

    subgraph obs["Observabilité"]
        LF["Langfuse<br/>traces LLM + coûts"]
        GRAF["Grafana · Loki<br/>Prometheus"]
        SENTRY["Sentry"]
    end

    subgraph ext["Fournisseurs externes"]
        LLM["Anthropic · Groq · OpenRouter"]
        IMG["fal.ai / Replicate"]
        TTS["ElevenLabs / Kokoro local"]
        SOC["TikTok · Instagram · YouTube"]
        STR["Stripe"]
    end

    WEB --> CF --> API
    API --> PG
    API --> RD
    API -.enqueue.-> WIO
    API -.enqueue.-> WCPU
    API <-.HTTP idempotent.-> N8N
    SCHED --> RD
    SCHED --> PG
    N8N --> API
    N8N --> SOC
    WIO --> PG
    WIO --> RD
    WIO --> R2
    WIO --> LLM
    WIO --> IMG
    WIO --> TTS
    WCPU --> R2
    WCPU --> PG
    API --> STR
    WIO --> LF
    API --> SENTRY
    WIO --> GRAF
```

## 2. Les cinq plans et leurs frontières

| Plan | Responsabilité | Ne fait jamais |
|---|---|---|
| **Présentation** (`apps/web`) | UI, gates HITL, preview, billing | Aucun appel direct à un fournisseur IA |
| **Contrôle** (`apps/api`) | Auth, quotas, création de jobs, machine à états, webhooks | Aucun traitement long (> 2 s) |
| **Orchestration** (`libs/core/pipeline` + `orchestration/n8n`) | Enchaînement des étapes, gates, reprise | Aucune logique d'agent |
| **Exécution** (`apps/worker`, `apps/renderer`) | Agents, appels modèles, média | Aucune décision produit |
| **Données** (PG / Redis / R2) | Persistance, cache, artefacts | — |

**Règle de dépendance** : les flèches ne remontent jamais.
`web → api → pipeline → agents → adapters → fournisseurs`.
Un agent ne connaît ni FastAPI ni n8n. Un adapter ne connaît pas le domaine.

## 3. Machine à états d'un job

C'est le cœur du système : elle porte la reprise, les gates et l'observabilité.

```mermaid
stateDiagram-v2
    [*] --> QUEUED
    QUEUED --> RUNNING : worker prend le lease
    RUNNING --> AWAITING_APPROVAL : gate HITL atteint
    AWAITING_APPROVAL --> RUNNING : approuvé / édité
    AWAITING_APPROVAL --> CANCELLED : rejeté
    AWAITING_APPROVAL --> RUNNING : expiration + politique auto_approve
    RUNNING --> RETRYING : erreur transitoire
    RETRYING --> RUNNING : backoff écoulé
    RETRYING --> FAILED : budget de retry épuisé
    RUNNING --> DEGRADED : repli fournisseur activé
    DEGRADED --> RUNNING
    RUNNING --> COMPLETED
    FAILED --> RUNNING : reprise manuelle ou WF-12
    COMPLETED --> [*]
    CANCELLED --> [*]
```

Chaque transition écrit une ligne dans `job_events` (append-only) : l'historique complet
d'un job est rejouable, ce qui rend le debug post-mortem possible sans logs.

## 4. Pipeline « idée → vidéo » (F1)

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant API as FastAPI
    participant P as Pipeline Engine
    participant A as Agents
    participant R as Renderer

    U->>API: POST /v1/jobs {type: idea_to_video, idea}
    API->>API: quota + budget check
    API-->>U: 202 {job_id} + flux SSE
    API->>P: enqueue(job)

    P->>A: ConceptAgent → angle, promesse, audience
    P->>A: ScriptAgent + HookAgent → script + 3 hooks
    P-->>U: GATE 1 — validation script
    U-->>P: approuvé (ou édité)

    P->>A: StoryboardAgent → découpage en scènes + prompts image
    P-->>U: GATE 2 — validation storyboard
    U-->>P: approuvé

    par Parallélisation
        P->>A: ImageAgent ×N scènes
    and
        P->>A: VoiceAgent → MP3 + word timings
    and
        P->>A: MusicAgent → piste libre de droits
    end

    P->>A: SubtitleAgent → ASS karaoké aligné
    P->>R: RenderAgent → ffmpeg concat + burn-in
    P->>A: QAAgent → durée, lisibilité, safe zones, policy
    P-->>U: GATE 3 — validation vidéo finale
    U-->>P: approuvé
    P->>API: job COMPLETED + asset publiable
```

## 5. Pipeline « ADN viral » (F2 → F4)

```mermaid
flowchart LR
    A["URL TikTok"] --> B["IngestAgent<br/>vidéo + métadonnées"]
    B --> C1["TranscriptionAgent<br/>whisper + timings mot"]
    B --> C2["SceneAgent<br/>détection de coupes"]
    B --> C3["VisionAgent<br/>keyframes → description"]
    B --> C4["AudioAgent<br/>BPM · énergie · silences"]
    C1 & C2 & C3 & C4 --> D["DNAExtractorAgent<br/>fusion multimodale"]
    D --> E{{"ViralDNA v1<br/>JSON validé par schéma"}}
    E --> F["DNAAbstractorAgent<br/>retire tout contenu<br/>→ StyleTemplate"]
    F --> G[("Bibliothèque d'ADN<br/>pgvector")]
    G --> H["DNATransferAgent<br/>StyleTemplate + nouveau sujet"]
    H --> I["Pipeline F1 contraint<br/>par le template"]
```

**Point clé** : `DNAAbstractorAgent` est une étape séparée et obligatoire. Elle supprime
noms propres, phrases, marques, visuels identifiables. Ce qui entre dans la bibliothèque
réutilisable est un **squelette**, jamais un contenu. C'est la traduction technique du
principe P5 et la mitigation du risque juridique R2.

## 6. Modèle de déploiement v1 (budget 80 €)

```mermaid
flowchart TB
    subgraph vps1["VPS-APP · Hetzner CX32 · 4 vCPU / 8 Go — 7,5 €/mois"]
        direction LR
        a1["Traefik"] --- a2["Next.js"] --- a3["FastAPI ×2"]
        a4["n8n main + 1 worker"] --- a5["PostgreSQL 16"] --- a6["Redis"]
        a7["Langfuse"] --- a8["Grafana/Loki"]
    end
    subgraph vps2["VPS-MEDIA · Hetzner CCX23 dédié · 4 vCPU / 16 Go — 27 €/mois"]
        direction LR
        b1["ARQ workers I/O ×50"] --- b2["ffmpeg workers ×2"]
        b3["faster-whisper"] --- b4["Kokoro TTS"]
    end
    vps1 <-->|"réseau privé Hetzner"| vps2
    vps2 --> r2[("Cloudflare R2")]
```

Le rendu et la transcription sont sur un **CPU dédié** (CCX) et non partagé : ffmpeg sur
vCPU mutualisé produit des temps de rendu erratiques qui cassent le SLO p95.

**Chemin de montée en charge**, sans changement d'architecture :
1. Ajouter des VPS-MEDIA (les workers sont sans état, ils tirent de Redis) → scaling horizontal linéaire.
2. Sortir PostgreSQL sur une instance managée quand le budget le permet.
3. Passer le rendu sur des instances *spot* GPU/CPU à la demande.
4. Remplacer le pipeline engine par Temporal si la durabilité devient critique ([ADR-002](./adr/002-orchestration.md)).

## 7. Multi-tenant

- Isolation **logique** : `org_id` sur chaque table, appliqué par Row-Level Security PostgreSQL — pas seulement par le code applicatif (défense en profondeur).
- Isolation **des files** : clé de file `queue:{tier}` — un compte gratuit qui lance 200 jobs ne bloque pas un compte payant.
- **Fair scheduling** : token bucket par `org_id` en amont de la file, pour éviter la famine.
- Isolation **des artefacts** : préfixe R2 `org/{org_id}/...` + URLs signées à durée courte.
