"""Tests pour les fonctions d'affichage de `pdz/cli.py`.

Ces fonctions ne sont exercées par aucun autre test — elles ne sont
appelées que depuis les commandes Typer, jamais importées ailleurs. C'est
justement ce qui a laissé passer une régression : `_resume_empreinte`
référençait encore `e.arc_emotionnel`/`e.retention` après le regroupement
de `EmpreinteCreative` en sous-objets (`e.psychologie.arc_emotionnel`), et
aurait fait planter `pdz charte` en production sans qu'aucun test ne le
détecte.
"""

from pathlib import Path

from pdz.cli import _resume_empreinte, references
from pdz.univers import (
    ChampInterprete,
    EmpreinteCreative,
    EmpreinteHook,
    EmpreinteNarrative,
    EmpreintePsychologie,
    EmpreinteVisuelle,
    Univers,
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


# ── pdz references (harnais de vidéos privées) ─────────────────────────────

FRUITS = Path(__file__).resolve().parent.parent / "univers" / "fruit-island.yaml"


def _empreinte_distincte(suffixe: str) -> EmpreinteCreative:
    champ = lambda v, c=0.8: ChampInterprete(valeur=v, confiance=c, observation="vu")
    return EmpreinteCreative(
        hook=EmpreinteHook(type=champ(f"hook-{suffixe}")),
        narrative=EmpreinteNarrative(structure=champ(f"structure-{suffixe}"), fin=champ(f"fin-{suffixe}")),
        psychologie=EmpreintePsychologie(arc_emotionnel=champ(f"emotion-{suffixe}"), retention=champ(f"retention-{suffixe}")),
        visuel=EmpreinteVisuelle(style=champ(f"style-{suffixe}")),
    )


def test_references_sans_dossier_ne_plante_pas(tmp_path, capsys):
    references(dossier=tmp_path / "nexiste-pas", verbeux=False)
    assert "Aucune vidéo" in capsys.readouterr().out


def test_references_relit_les_chartes_deja_faites_sans_rappeler_lia(tmp_path, capsys):
    """Une charte déjà produite (`<nom>.univers.yaml` à côté de la vidéo,
    jamais dans `univers/` qui est publié) est relue, jamais reproduite :
    relancer la commande ne repaie pas une analyse déjà faite — et ce test
    ne fait donc aucun appel IA."""
    for nom in ["alpha", "beta", "gamma"]:
        video = tmp_path / f"{nom}.mp4"
        video.write_bytes(b"")
        u = Univers.charger(FRUITS)
        u.id = nom
        u.empreinte_creative = _empreinte_distincte(nom)
        u.sauver(video.with_suffix(".univers.yaml"))

    references(dossier=tmp_path, verbeux=False)
    sortie = capsys.readouterr().out
    assert sortie.count("déjà chartée") == 3
    assert "3 vidéo" in sortie
    assert "Pas de répétition" in sortie


def test_references_lit_la_mecanique_attendue_annotee_a_la_main(tmp_path, capsys):
    video = tmp_path / "solo.mp4"
    video.write_bytes(b"")
    (tmp_path / "solo.yaml").write_text(
        "mecanique_attendue: pose une question jamais résolue\n", encoding="utf-8",
    )
    u = Univers.charger(FRUITS)
    u.id = "solo"
    u.empreinte_creative = _empreinte_distincte("solo")
    u.sauver(video.with_suffix(".univers.yaml"))

    references(dossier=tmp_path, verbeux=False)
    sortie = capsys.readouterr().out
    assert "pose une question jamais résolue" in sortie
    # Une seule empreinte : pas assez pour un diagnostic de diversité.
    assert "il en faut au moins 3" in sortie
