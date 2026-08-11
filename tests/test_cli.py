"""Tests pour les fonctions d'affichage de `pdz/cli.py`.

Ces fonctions ne sont exercées par aucun autre test — elles ne sont
appelées que depuis les commandes Typer, jamais importées ailleurs. C'est
justement ce qui a laissé passer une régression : `_resume_empreinte`
référençait encore `e.arc_emotionnel`/`e.retention` après le regroupement
de `EmpreinteCreative` en sous-objets (`e.psychologie.arc_emotionnel`), et
aurait fait planter `pdz charte` en production sans qu'aucun test ne le
détecte.
"""

from pdz.cli import _resume_empreinte
from pdz.univers import (
    ChampInterprete,
    EmpreinteCreative,
    EmpreinteHook,
    EmpreinteNarrative,
    EmpreintePsychologie,
    EmpreinteVisuelle,
)


def _empreinte_complete() -> EmpreinteCreative:
    champ = lambda v, c=0.8: ChampInterprete(valeur=v, confiance=c, observation="vu dans la référence")
    return EmpreinteCreative(
        hook=EmpreinteHook(type=champ("question impossible")),
        narrative=EmpreinteNarrative(structure=champ("mise en place"), fin=champ("révélation ouverte")),
        psychologie=EmpreintePsychologie(arc_emotionnel=champ("curiosité, tension"), retention=champ("chaque plan retient une info")),
        visuel=EmpreinteVisuelle(cadrage=champ("varie large puis serré")),
        principes_reutilisables=["pose une question avant la 3e seconde"],
    )


def test_resume_empreinte_ne_plante_pas_et_montre_les_groupes():
    resume = _resume_empreinte(_empreinte_complete())
    assert "question impossible" in resume
    assert "curiosité, tension" in resume
    assert "chaque plan retient une info" in resume
    assert "varie large puis serré" in resume
    assert "pose une question avant la 3e seconde" in resume
