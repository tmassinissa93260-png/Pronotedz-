# ADR-005 — Embeddings : bge-m3 local + pgvector

**Statut** : Proposé · **Date** : 2026-08-05

## Contexte

Besoin d'embeddings pour : recherche de StyleTemplates par similarité, bibliothèque de
hooks, détection d'auto-plagiat, cache sémantique. Volume estimé v1 : 50 k à 200 k documents.

## Options

**A. Base vectorielle dédiée** (Pinecone, Qdrant Cloud, Weaviate)
✅ Performances à grande échelle. ❌ 20–70 €/mois, un système de plus à exploiter, et une
seconde source de vérité à synchroniser avec PostgreSQL.

**B. pgvector + API d'embeddings hébergée** (voyage-3-lite, OpenAI text-embedding-3)
✅ Qualité, zéro exploitation. ❌ coût par requête, latence réseau sur chaque recherche,
et une dépendance externe supplémentaire dans un chemin critique.

**C. pgvector + bge-m3 auto-hébergé sur le VPS-MEDIA** ✅

## Décision

Option C. `bge-m3` (multilingue, 1024 dimensions, ~2,2 Go en fp16) servi en local via
`sentence-transformers`, index HNSW dans pgvector.

Recherche **hybride** : vectoriel + `pg_trgm` lexical, fusion par Reciprocal Rank Fusion.
Sur des requêtes courtes et spécialisées (noms de niches, formats), le lexical rattrape
les faiblesses du vectoriel — une recherche purement vectorielle déçoit systématiquement
sur ce type de corpus.

## Conséquences

**Positif** — 0 €, pas de latence réseau, pas de fuite de contenu utilisateur vers un
tiers, une seule source de vérité, transactions ACID entre la donnée et son embedding
(un document et son vecteur ne peuvent pas désynchroniser).

**Négatif** — ~2,5 Go de RAM sur le VPS-MEDIA ; pgvector devient plus lent au-delà de
~1 M vecteurs ; l'embedding est calculé sur CPU (~40 ms/document, acceptable au volume visé).

**Seuil de révision** — au-delà de 500 k vecteurs ou si la latence p95 de recherche dépasse
200 ms, migrer vers Qdrant auto-hébergé (et non un service managé, pour rester dans le budget).
