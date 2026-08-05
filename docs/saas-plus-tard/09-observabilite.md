# 09 — Logs, traces, métriques et coûts

## 1. Les quatre signaux

| Signal | Outil | Auto-hébergé | Question à laquelle il répond |
|---|---|---|---|
| **Logs structurés** | Loki + Promtail | ✅ | « que s'est-il passé exactement ? » |
| **Traces distribuées** | OpenTelemetry → Tempo (ou Langfuse) | ✅ | « où est passé le temps ? » |
| **Traces LLM** | Langfuse | ✅ | « quel prompt, quel modèle, quel coût, quelle sortie ? » |
| **Métriques** | Prometheus + Grafana | ✅ | « est-ce que ça va bien globalement ? » |
| **Erreurs** | Sentry (plan gratuit) | ☁️ | « quel bug, quelle stack, quel utilisateur ? » |

Tout est auto-hébergé sur le VPS-APP, sauf Sentry (gratuit jusqu'à 5 k événements/mois).
Budget observabilité : **0 €**.

## 2. Corrélation — une seule règle

**Tout objet observable porte `trace_id`, `job_id`, `org_id`, `step_key`.**

`trace_id` est généré à l'entrée API, propagé dans le payload de la file, dans les
en-têtes HTTP vers n8n, dans les tags Langfuse et dans chaque ligne de log. Résultat :
depuis un ticket support « ma vidéo est bizarre », on retrouve en une requête le job,
ses étapes, les prompts exacts, les sorties de modèle, le coût et les artefacts.

Sans cette discipline, un système à 18 agents et 17 workflows est indébogable.

## 3. Format de log

JSON structuré, un événement par ligne, jamais de `print`.

```json
{
  "ts": "2026-08-05T10:23:45.123Z",
  "level": "info",
  "msg": "step.completed",
  "trace_id": "01J...", "job_id": "job_...", "org_id": "org_...",
  "step_key": "generate_images", "agent_id": "image_agent", "agent_version": "1.2.0",
  "model_id": "flux-schnell", "prompt_version": "creative/image_prompt@1.4.0",
  "attempt": 1, "duration_ms": 8420, "cost_eur": 0.0224,
  "cache": { "layer": "miss" },
  "outputs": { "artifact_ids": ["art_...", "art_..."] }
}
```

**Règles de rédaction (PII / secrets)** :
- Jamais de clé d'API, de token OAuth, de mot de passe — filtre applicatif *et* filtre Promtail (défense en profondeur).
- Le contenu utilisateur (idée, script) n'est **pas** dans Loki : il est dans PostgreSQL,
  référencé par ID. Loki est purgé à 14 jours ; la donnée métier suit la politique RGPD.
- Les URLs R2 sont loguées sans signature.

Niveaux : `debug` (dev), `info` (transitions d'état, appels modèle), `warn` (retry,
dégradation, disjoncteur), `error` (échec d'étape), `critical` (job perdu, budget dépassé).

## 4. Traces

Une trace = un job. Spans imbriqués :

```
job.idea_to_video                                    6m12s   0,17 €
├── step.concept                                       3,1s   0,004 €
│   └── llm.claude-haiku-4-5                           2,9s   1 240 in / 380 out
├── step.script                                        8,4s   0,031 €
│   └── llm.claude-sonnet-4-5                          8,1s   3 100 in / 1 450 out  (cached: 2 200)
├── gate.script                                       4m02s   ← attente humaine, exclue du SLO
├── step.storyboard                                    5,2s   0,006 €
├── step.images (fan-out ×8)                          22,6s   0,022 €
│   ├── image.flux-schnell[0..7]                     2,1–3,4s
├── step.voice                                         6,8s   0,000 €  (kokoro local)
├── step.subtitles                                     0,9s   0,000 €
├── step.render                                       48,2s   0,000 €  (ffmpeg)
└── step.qa                                            4,4s   0,007 €
```

Deux choses lisibles immédiatement sur cette vue : **où est la latence** (le rendu et
le fan-out d'images) et **où est le coût** (le script). Ce sont les deux leviers
d'optimisation, et ils ne sont pas au même endroit.

## 5. Métriques clés (Prometheus)

**Techniques**
```
pdz_jobs_total{type,status}
pdz_job_duration_seconds{type}            histogram
pdz_step_duration_seconds{agent}          histogram
pdz_step_failures_total{agent,error_category}
pdz_queue_depth{queue}
pdz_queue_wait_seconds{queue}             histogram
pdz_worker_utilization{worker_type}
pdz_cache_hits_total{layer,agent}
pdz_circuit_breaker_state{provider}
pdz_model_latency_seconds{model_id}       histogram
pdz_model_errors_total{model_id,code}
pdz_render_duration_seconds
```

**Métier & coûts**
```
pdz_videos_generated_total{org_plan}
pdz_cost_eur_total{model_id,agent,org_id}       counter
pdz_cost_per_video_eur                          histogram
pdz_gate_response_seconds{gate_type}            histogram
pdz_gate_timeouts_total{gate_type}
pdz_dna_extractions_total
pdz_publications_total{platform,status}
pdz_credits_consumed_total{org_id}
```

`pdz_gate_response_seconds` est une métrique **produit** déguisée en métrique technique :
si les utilisateurs mettent 6 heures à valider un script, le SLO de latence bout-en-bout
n'a aucun sens et il faut repenser le produit (notifications, auto-pilot), pas l'infra.

## 6. Tableaux de bord Grafana (4)

1. **Santé système** — files, latence p50/p95/p99 par étape, taux d'erreur, disjoncteurs, CPU/RAM/disque.
2. **Coûts** — €/jour, €/vidéo, répartition par modèle/agent/org, projection fin de mois vs budget 80 €, top 10 des orgs coûteuses.
3. **Qualité** — score QA, taux de rejet aux gates, taux de régénération, taux de dégradation, hit ratios de cache.
4. **Produit** — vidéos générées, ADN extraits, publications, funnel gate→publication, rétention.

## 7. Alertes (Alertmanager → Discord/email)

| Sévérité | Condition | Action |
|---|---|---|
| **P1** | Coût journalier > 150 % de la moyenne 7 j | coupure automatique des jobs non payants + alerte |
| **P1** | Aucun job terminé depuis 15 min alors que la file > 0 | réveil |
| **P1** | Erreur 5xx API > 5 % sur 5 min | réveil |
| **P1** | Disque VPS > 90 % | réveil (n8n executions, artefacts temporaires) |
| **P2** | Disjoncteur `OPEN` sur un fournisseur primaire | vérifier le repli |
| **P2** | Taux d'échec d'étape > 10 % sur 30 min | investiguer |
| **P2** | Profondeur de file > 200 pendant 10 min | scaler les workers |
| **P3** | Hit ratio cache < 50 % (attendu > 85 %) | régression probable de clé |
| **P3** | Éval de prompt en régression (WF-13) | bloquer la promotion |

Le budget étant l'enjeu principal, **l'alerte de coût est en P1 avec coupure automatique**.
Un bug de boucle infinie sur un appel LLM peut consommer un mois de budget en une nuit ;
c'est le scénario de perte financière le plus probable du projet.

## 8. Audit

`audit_logs` (append-only, rétention 1 an) enregistre tout ce qui doit être opposable :
décisions de gate humain, publications, changements de plan, accès admin, promotions de
prompt, suppressions RGPD, décisions du `PolicyAgent`. Distinct des logs applicatifs :
autre durée de vie, autre exigence d'intégrité, autre public.
