# ADR-003 — Pas de framework multi-agents

**Statut** : Proposé · **Date** : 2026-08-05

## Contexte

18 agents à orchestrer. LangGraph, CrewAI, AutoGen, Pydantic-AI proposent des
abstractions toutes faites.

## Options

**A. LangGraph** — graphes d'états, checkpointing intégré.
Mais son checkpointer sérialise un état global ; il ne connaît pas nos artefacts adressés
par contenu, ni le budget par étape, ni la reprise cross-déploiement. On se retrouverait
à contourner l'abstraction. Dépendance lourde à LangChain.

**B. CrewAI / AutoGen** — conçus pour la collaboration émergente entre agents.
Notre pipeline est **connu, borné et déterministe dans sa structure**. La non-déterminisme
est dans le contenu, pas dans l'enchaînement. Payer le coût d'un framework d'émergence
pour un pipeline fixe est un mauvais échange : plus de tokens, moins de prévisibilité,
coût moins contrôlable.

**C. Pydantic-AI** — léger, typé, proche de notre philosophie.
Sérieux candidat, mais impose son abstraction de modèle, ce qui entre en concurrence avec
notre Model Registry déclaratif (principe P3).

**D. Contrat `Agent` maison + Model Registry** ✅

## Décision

Option D. Une classe de base `Agent` (~80 lignes) + un `AgentSpec` déclaratif en YAML.
Le moteur fournit cache, retry, budget, tracing et checkpointing en middleware ; l'agent
ne contient que sa logique propre (~30 lignes).

Les SDK officiels des fournisseurs (`anthropic`, `openai`) sont utilisés directement dans
`libs/providers`, sans couche d'abstraction tierce.

## Conséquences

**Positif** — surface de dépendance minimale ; contrôle total sur le coût et la reprise,
qui sont nos deux contraintes fortes ; pas de rupture lors des montées de version d'un
framework tiers ; comportement entièrement prévisible.

**Négatif** — pas de « batteries incluses » (pas d'UI de debug de graphe fournie) ;
il faut écrire soi-même le middleware. Mitigé par Langfuse, qui donne la visualisation
de trace sans imposer de framework d'orchestration.

**Note** — cette décision est facile à réviser dans un sens (adopter un framework plus
tard) et difficile dans l'autre. C'est la bonne direction pour un choix incertain.
