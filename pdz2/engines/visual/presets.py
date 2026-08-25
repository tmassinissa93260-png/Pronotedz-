"""Préréglages de style, déclarés par ton.

Ce sont des **tables publiées**, pas des générations. Le compilateur n'invente
aucune chaîne au moment où il tourne : il en choisit une, écrite ici, et le
signale dans ses notes. Un style *par défaut* n'est jamais un style *décidé* —
la décision, quand elle est prise, arrive par `DirectorBrief.visual_style`.

Aucun nom de moteur, de modèle ou de fournisseur n'a sa place dans ce fichier.
La bible décrit une intention visuelle ; c'est aux adaptateurs, bien plus tard,
de savoir comment l'obtenir.
"""

from __future__ import annotations

from pdz2.contracts.direction import VisualStyleDecision
from pdz2.contracts.enums import Pacing, Tone

__all__ = ["STYLE_PRESETS", "CAMERA_LANGUAGE", "DEPTH_OF_FIELD", "preset_for"]

STYLE_PRESETS: dict[Tone, VisualStyleDecision] = {
    Tone.DOCUMENTARY: VisualStyleDecision(
        style="documentaire technique, coupe transparente, rendu physiquement plausible",
        lighting="lumière rasante d'atelier, une source dominante, ombres tenues",
        palette=["#0F1B2A", "#1E3A5F", "#C9752B", "#E8E4DC"],
        lens_language="focales normales, 35 à 50 mm, peu de distorsion",
        materials=["métal brossé", "cuivre", "verre dépoli", "polymère mat"],
        texture="grain fin, surfaces réelles, pas de brillance plastique",
        environment="atelier neutre, fond sombre non distrayant",
        graphics="repères vectoriels sobres, flèches et cotes fines",
        typography_family="Inter",
    ),
    Tone.EXPLANATORY: VisualStyleDecision(
        style="schéma animé lisible, aplats francs, hiérarchie claire",
        lighting="éclairage diffus uniforme, aucune ombre portée",
        palette=["#132235", "#2E6FA7", "#F2B134", "#F7F7F5"],
        lens_language="vue orthographique ou focale longue, perspective réduite",
        materials=["aplats", "traits pleins", "hachures légères"],
        texture="surfaces plates, aucun grain",
        environment="fond uni, aucun décor",
        graphics="pictogrammes cohérents, légendes courtes",
        typography_family="Inter",
    ),
    Tone.CINEMATIC: VisualStyleDecision(
        style="image cinéma, contraste marqué, cadres tenus",
        lighting="clair-obscur, contre-jour, une source froide et une chaude",
        palette=["#080B12", "#243447", "#B4552D", "#D9D2C5"],
        lens_language="focales longues, 50 à 85 mm, bokeh franc",
        materials=["métal patiné", "poussière en suspension", "verre rayé"],
        texture="grain argentique léger, halations douces",
        environment="volumes profonds, arrière-plans qui respirent",
        graphics="incrustations minimales, jamais sur le sujet",
        typography_family="Inter",
    ),
    Tone.URGENT: VisualStyleDecision(
        style="reportage nerveux, cadres serrés, contraste élevé",
        lighting="sources dures, températures mêlées",
        palette=["#101010", "#3A0E0E", "#E2482D", "#F0EDE8"],
        lens_language="grands angles, 24 à 35 mm, distorsion assumée",
        materials=["surfaces usées", "béton", "acier oxydé"],
        texture="grain marqué, netteté agressive",
        environment="espaces resserrés, hors-champ actif",
        graphics="cartons brefs, alignés au bord de cadre",
        typography_family="Inter",
    ),
    Tone.CONTEMPLATIVE: VisualStyleDecision(
        style="plans longs, composition centrée, calme",
        lighting="lumière naturelle douce, heure bleue",
        palette=["#1A2430", "#46606F", "#9FB3AC", "#EFEAE1"],
        lens_language="focales normales, grande ouverture, netteté sélective",
        materials=["bois", "textile", "eau", "brume"],
        texture="grain très fin, transitions douces",
        environment="paysages ouverts, vide assumé",
        graphics="aucun élément graphique, ou presque",
        typography_family="Inter",
    ),
    Tone.PLAYFUL: VisualStyleDecision(
        style="illustration vive, formes simples, énergie",
        lighting="éclairage plein, ombres colorées",
        palette=["#1B1F3B", "#3E63DD", "#F5A524", "#FDF6EC"],
        lens_language="focales courtes, perspectives exagérées",
        materials=["aplats saturés", "contours épais"],
        texture="surfaces lisses, aucun grain",
        environment="décors stylisés, peu d'éléments",
        graphics="onomatopées et repères ludiques, jamais illisibles",
        typography_family="Inter",
    ),
}

CAMERA_LANGUAGE: dict[Pacing, str] = {
    Pacing.SLOW: "caméra posée, mouvements longs et continus, jamais d'à-coup",
    Pacing.MEASURED: "caméra stable, poussées lentes, recadrages discrets",
    Pacing.BRISK: "caméra active, poussées franches, changements d'axe nets",
    Pacing.RAPID: "caméra vive, mouvements courts, coupes sur le mouvement",
}

DEPTH_OF_FIELD: dict[Pacing, str] = {
    Pacing.SLOW: "profondeur généreuse, arrière-plan lisible",
    Pacing.MEASURED: "profondeur moyenne, sujet détaché sans isolement",
    Pacing.BRISK: "profondeur courte, sujet isolé, bascules rapides",
    Pacing.RAPID: "profondeur très courte, lecture immédiate du sujet",
}


def preset_for(tone: Tone) -> VisualStyleDecision:
    """Préréglage déclaré pour un ton. Aucune génération, une table."""
    return STYLE_PRESETS[tone]
