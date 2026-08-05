# 03 — Agents spécialisés

## 1. Ce qu'est un « agent » ici

Un agent est une **unité de travail typée, déterministe dans son contrat, non
déterministe dans son exécution**. Ce n'est pas forcément une boucle ReAct : la
majorité des agents sont des appels LLM structurés à un tour. Trois seulement
(`SupervisorAgent`, `QAAgent`, `IngestAgent`) sont de vraies boucles avec outils.

> **Décision** : on n'utilise *pas* un framework multi-agents généraliste
> (CrewAI, AutoGen, LangGraph). Le pipeline est connu, borné et métier ; un moteur
> d'étapes maison de ~400 lignes donne un contrôle total sur les checkpoints, le
> budget et la reprise — les trois choses que ces frameworks gèrent mal.
> Voir [ADR-003](./adr/003-framework-agents.md).

## 2. Contrat commun — `AgentSpec`

Tout agent déclare, en donnée :

```yaml
id: dna_extractor
version: 2.1.0
description: "Fusionne les signaux multimodaux en un objet ViralDNA"

capability: text.reason            # ce qu'il demande au registry de modèles
model_policy:
  primary:   tier.reasoning        # alias résolu par models.yaml
  fallbacks: [tier.balanced, tier.fast]
  max_cost_eur: 0.08               # plafond dur pour une exécution
  timeout_s: 90

prompt_ref: dna/extract_dna@^2.1.0 # semver range → résolu au démarrage du job

input_schema:  schemas/dna_extractor_in.json
output_schema: schemas/viral_dna_v1.json
output_mode: structured            # sortie contrainte, validée, pas de parsing best-effort

tools: []                          # aucun outil → pas de boucle

cache:
  enabled: true
  key: [transcript_sha, scenes_sha, audio_features_sha, prompt_version, model_id]
  ttl: 30d

retry:
  policy: exponential
  max_attempts: 3
  retry_on: [RateLimit, ProviderTimeout, SchemaValidation]

checkpoint: true                   # persiste sa sortie → reprise possible ici
gate: null                         # pas de validation humaine après cet agent
observability:
  langfuse_tags: [dna, extraction]
```

Conséquences directes :
- **Ajouter un agent** = un YAML + une classe de 30 lignes. Pas de modification du moteur.
- **Tester un agent** = fournir un input JSON, vérifier la sortie contre le schéma + évals.
- **Le cache, le retry, le budget, le tracing sont gérés par le moteur**, pas par l'agent.
  L'agent ne contient que sa logique propre.

## 3. Catalogue des 18 agents

### Famille A — Analyse (ingestion & compréhension)

| Agent | Rôle | Capacité | Modèle cible v1 | Sortie |
|---|---|---|---|---|
| **A1 · IngestAgent** | Récupère la vidéo source + métadonnées, normalise (9:16, 30 fps), stocke en R2 | `tool.exec` | yt-dlp / upload direct | `source_video` |
| **A2 · TranscriptionAgent** | Transcription + timings **au mot** + diarisation légère | `audio.stt` | Groq whisper-large-v3-turbo (repli faster-whisper local) | `transcript` |
| **A3 · SceneAgent** | Détection de coupes, durée de chaque plan, densité de montage | `tool.exec` | PySceneDetect (ffmpeg) — **aucun LLM** | `scene_analysis` |
| **A4 · VisionAgent** | Décrit les keyframes : cadrage, mouvement, texte à l'écran, palette | `vision.describe` | Claude Haiku 4.5 vision, 1 keyframe/plan | `visual_analysis` |
| **A5 · AudioAgent** | BPM, énergie, silences, loudness (LUFS), ducking musique/voix | `tool.exec` | librosa / ffmpeg — **aucun LLM** | `audio_features` |

> Note de coût : A3 et A5 sont **déterministes et gratuits**. Beaucoup d'architectures
> naïves envoient tout à un LLM ; ici le rythme de montage et le BPM sont mesurés,
> pas devinés. C'est plus juste *et* 100× moins cher.

### Famille B — ADN viral

| Agent | Rôle | Modèle cible | Note |
|---|---|---|---|
| **B1 · DNAExtractorAgent** | Fusionne A2–A5 en un `ViralDNA` validé par schéma | Claude Sonnet 4.5 | Le seul agent « cher » de la chaîne d'analyse |
| **B2 · DNAAbstractorAgent** | Supprime tout contenu identifiable → `StyleTemplate` réutilisable | Claude Haiku 4.5 | **Obligatoire, non contournable** — barrière juridique |
| **B3 · DNAScorerAgent** | Note l'ADN (force du hook, rétention estimée, transférabilité) + embedding | Haiku + embedding | Alimente la recherche par similarité |
| **B4 · DNATransferAgent** | Applique un `StyleTemplate` à un sujet nouveau → brief contraint | Claude Sonnet 4.5 | Produit des *contraintes*, pas du contenu |

### Famille C — Création

| Agent | Rôle | Modèle cible |
|---|---|---|
| **C1 · ConceptAgent** | Idée brute → angle, promesse, audience, format | Haiku 4.5 |
| **C2 · HookAgent** | Génère 3–5 hooks concurrents + auto-notation | Sonnet 4.5 |
| **C3 · ScriptAgent** | Script scène par scène, respectant WPM/durées imposées par l'ADN | Sonnet 4.5 |
| **C4 · StoryboardAgent** | Script → scènes visuelles + prompts image (style cohérent, seed fixe) | Haiku 4.5 |
| **C5 · CopyAgent** | Titre, description, hashtags, CTA, variantes par plateforme | Haiku 4.5 |

### Famille D — Production

| Agent | Rôle | Fournisseur v1 |
|---|---|---|
| **D1 · ImageAgent** | Génère les visuels, cohérence de style, retries sur échec de policy | fal.ai FLUX schnell / dev |
| **D2 · VoiceAgent** | TTS + timings mot + normalisation loudness (-14 LUFS) | Kokoro local (défaut) / ElevenLabs (premium) |
| **D3 · MusicAgent** | Sélection dans une banque libre de droits, matching BPM/émotion | Banque locale + embeddings — **pas de génération** |
| **D4 · SubtitleAgent** | Sous-titres karaoké ASS, découpage lisible, safe zones | libass — déterministe |
| **D5 · RenderAgent** | Montage final : timings, transitions, burn-in, export | ffmpeg (`RenderEngine`) |

### Famille E — Qualité & distribution

| Agent | Rôle |
|---|---|
| **E1 · QAAgent** | Vérifie durée, sync A/V, lisibilité, safe zones, images noires, silences ; **peut relancer une étape** (boucle avec outils) |
| **E2 · PolicyAgent** | Conformité plateformes + politiques IA (violence, santé, finance, mineurs) + détection de similarité excessive avec la source |
| **E3 · PublisherAgent** | Publication multi-réseaux, adaptation par plateforme, planification |

### Famille F — Méta

| Agent | Rôle |
|---|---|
| **F1 · SupervisorAgent** | Choisit le pipeline, arbitre en cas d'échec répété, décide dégradation vs abandon. Seul agent autorisé à modifier le plan d'exécution |
| **F2 · CostGuardianAgent** | Non-LLM. Suit le budget par job/org, bloque, déclenche les replis moins chers |
| **F3 · FeedbackAgent** | Corrèle les performances réelles (vues, rétention) aux ADN et prompts utilisés → réinjecte dans la mémoire procédurale |

**Total : 18 agents**, dont **6 sans aucun appel LLM** (A3, A5, D3, D4, D5, F2).
C'est délibéré : chaque appel LLM évité est du coût, de la latence et de la variance en moins.

## 4. Le schéma `ViralDNA` — cœur du produit

C'est l'actif principal du SaaS. Il est versionné (`schema_version`) et migrable.

```jsonc
{
  "schema_version": "1.0",
  "identity":   { "niche": "...", "format": "talking_head|voiceover_broll|...",
                  "archetype": "story|listicle|reveal|tutorial|rant|pov" },

  "hook": {
    "type": "question|shock|negation|number|pov|controversy|visual",
    "duration_ms": 1800,
    "first_words_pattern": "…",          // patron abstrait, pas la phrase
    "visual_device": "zoom_in|jump_cut|text_slam|face_close",
    "curiosity_gap": 0.0-1.0,
    "pattern_interrupt_at_ms": [0, 900]
  },

  "structure": {
    "acts": [{ "name": "setup|tension|payoff|cta",
               "start_ratio": 0.0, "end_ratio": 0.15, "purpose": "…" }],
    "beats": [{ "t_ms": 0, "type": "hook|proof|twist|loop_open|loop_close" }],
    "open_loops": 2, "payoff_position_ratio": 0.78
  },

  "pacing": {                              // MESURÉ, pas estimé
    "total_duration_ms": 31200,
    "shot_count": 14,
    "avg_shot_duration_ms": 2228,
    "shot_duration_p10_p90_ms": [900, 4200],
    "cuts_per_minute": 27,
    "tempo_curve": [0.4, 0.7, 0.9, 0.6, 1.0]   // normalisé, 5 segments
  },

  "narration": {
    "wpm": 168, "pause_ratio": 0.12,
    "tone": "confident|intimate|urgent|playful",
    "energy_curve": [0.6, 0.8, 0.7, 1.0],
    "emphasis_pattern": "start_of_sentence|keyword_stress"
  },

  "visual": {
    "color_palette": ["#…"], "contrast": "high",
    "camera_moves": ["static", "push_in"],
    "text_overlay": { "style": "bold_center_karaoke", "words_per_card": 3,
                      "position_ratio": 0.62 },
    "broll_ratio": 0.7, "transitions": ["hard_cut", "whip"]
  },

  "audio": { "music_genre": "…", "bpm": 128, "music_voice_ratio_db": -14,
             "sfx_density_per_min": 6, "beat_aligned_cuts_ratio": 0.55 },

  "emotion": {
    "primary": ["curiosity", "surprise"],
    "valence_curve": [0.2, -0.3, 0.1, 0.8],
    "arousal_curve": [0.7, 0.9, 0.6, 1.0]
  },

  "cta": { "type": "follow|comment|save|link", "placement_ratio": 0.92,
           "wording_pattern": "imperative_short", "on_screen": true },

  "constraints": { "aspect_ratio": "9:16", "safe_zones": {...}, "max_duration_ms": 60000 },

  "confidence": { "overall": 0.82, "per_section": { "pacing": 0.95, "emotion": 0.61 } }
}
```

Deux détails qui comptent :

- **`confidence` par section.** Le rythme est mesuré (confiance ~0,95), l'émotion est
  inférée par LLM (confiance ~0,6). L'UI affiche cette différence ; le `DNATransferAgent`
  pondère les contraintes par leur confiance. Sans ça, on transfère du bruit.
- **Ratios plutôt que timecodes absolus** dans `structure` et `cta` : l'ADN d'une vidéo
  de 60 s devient transférable à une vidéo de 25 s sans recalcul.

## 5. Comment ajouter un agent (procédure)

1. `libs/prompts/catalog/<famille>/<nom>@1.0.0.yaml` — le prompt.
2. `libs/agents/<famille>/<nom>.py` — la classe, sous-classe de `Agent`, ~30 lignes.
3. `libs/agents/specs/<nom>.yaml` — l'`AgentSpec`.
4. JSON Schema d'entrée et de sortie.
5. Au moins 5 cas d'éval dans `libs/prompts/evals/<nom>/`.
6. Référencer l'agent dans une définition de pipeline.

Aucune modification du moteur, de l'API ou du frontend n'est requise.
