# Pronotedz

SaaS de génération automatique de vidéos courtes (TikTok / Reels / Shorts) avec
extraction et transfert d'**ADN viral**, validation humaine et publication multi-réseaux.

> **État actuel : phase de conception.** Aucun code applicatif n'est écrit.
> L'architecture complète est proposée et attend validation.

## 👉 [Lire l'architecture](./docs/architecture/README.md)

- [Décisions à prendre avant de coder](./docs/architecture/DECISIONS-A-PRENDRE.md) — 9 points bloquants ou structurants
- [Risques](./docs/architecture/12-risques.md) — 13 risques identifiés, 4 critiques
- [Budget 80 €/mois](./docs/architecture/10-budget.md) — ventilation et coût unitaire par vidéo
- [Roadmap](./docs/architecture/13-evolutions.md#6-roadmap-de-mise-en-œuvre) — ~12 semaines jusqu'à un SaaS commercialisable

## En bref

| | |
|---|---|
| **Frontend** | Next.js 15, TypeScript, Tailwind, shadcn/ui |
| **Backend** | FastAPI (Python 3.12), Pydantic v2, SQLAlchemy 2 |
| **Files & workers** | ARQ + Redis, workers I/O et média séparés |
| **Données** | PostgreSQL 16 + pgvector, Cloudflare R2 |
| **Orchestration** | Moteur de pipeline maison + n8n en périphérie |
| **Rendu** | FFmpeg + libass |
| **Agents** | 18 agents spécialisés derrière un contrat unique |
| **Observabilité** | Langfuse, Grafana/Loki/Prometheus, Sentry |
| **Infra** | 2 VPS Hetzner, Docker Compose, Traefik |
