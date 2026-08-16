"""Recoupe les champs du Visual Contract entre eux, avant toute génération.

`ShotPromptWriter` décide de plus en plus de choses dans le même appel
(`relations`, `abstractions`, `risques_predits`, `geometrie`…) — rien ne
garantit pourtant que ces décisions restent COHÉRENTES entre elles : une
`relation` peut viser un objet qui n'apparaît dans aucune autre liste, un
risque de marque déjà détecté par `pdz.production.risque_prompt` peut ne
recevoir aucune `abstraction` qui le couvre. Ce sont des incohérences
internes au texte du contrat, pas des défauts de l'image — elles se
détectent donc ici, en Python, avant qu'un centime ne soit dépensé chez le
fournisseur d'image.

Distinct de `pdz.production.qa_images` (QA VISION, après génération, sur
l'image réelle) : ceci reste au niveau de la PRÉDICTION — un texte qui se
contredit lui-même — jamais une preuve visuelle. Même discipline que
`pdz.production.cadrage.verifier_diversite()` : une liste de FAITS bruts,
diagnostic seulement, jamais un score, jamais un blocage, jamais une
relance.
"""

from __future__ import annotations

from pdz.production.contrat_visuel import ContratVisuel


def verifier(contrat: ContratVisuel) -> list[str]:
    """Les incohérences internes détectées sur ce contrat — liste vide si
    rien à signaler, le cas le plus courant.

    Chaque vérification ne se déclenche que si la donnée qu'elle recoupe
    existe déjà (pas de `geometrie` → pas de vérification de position, pas
    de `risques_marque` → pas de vérification de traitement) : silencieux
    quand il n'y a rien à dire, jamais un bruit de fond sur un plan simple.
    """
    faits: list[str] = []

    if not contrat.qui.strip():
        faits.append("sujet manquant")
    if not contrat.quoi.strip():
        faits.append("action manquante")

    if contrat.geometrie:
        positionnes = {g.get("entite", "").strip().lower() for g in contrat.geometrie}
        non_positionnes = [e for e in contrat.avec_quoi
                           if e.strip().lower() not in positionnes]
        if non_positionnes:
            faits.append(f"objet(s) non positionné(s) : {', '.join(non_positionnes)}")

    connus = {e.strip().lower() for e in contrat.avec_quoi + contrat.avec_quoi_secondaire}
    orphelines = [r.get("cible", "") for r in contrat.relations
                 if r.get("cible", "").strip().lower() not in connus]
    if orphelines:
        faits.append(f"relation(s) orpheline(s) : {', '.join(orphelines)}")

    if contrat.risques_marque:
        couverts = {a.get("concept", "").strip().lower() for a in contrat.abstractions} | \
                   {e.strip().lower() for e in contrat.ne_doit_pas_apparaitre}
        non_traites = [m for m in contrat.risques_marque
                       if m.strip().lower() not in couverts]
        if non_traites:
            faits.append(f"risque de marque non traité : {', '.join(non_traites)}")

    return faits
