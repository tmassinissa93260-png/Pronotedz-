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

import pdz.agents.ecriture.script as script_module
from pdz.cli import avant_apres, _resume_empreinte, references
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


# ── pdz avant-apres (rapport de transfert) ──────────────────────────────────

def test_avant_apres_sans_charte_prealable_echoue_proprement(tmp_path):
    import typer
    try:
        avant_apres(reference="inconnue", sujet="x", dossier=tmp_path,
                   duree=45, sortie=None, verbeux=False)
    except typer.Exit as e:
        assert e.exit_code == 1
    else:
        raise AssertionError("aurait dû lever typer.Exit(1)")


def test_avant_apres_genere_le_rapport_sans_appel_ia(tmp_path, monkeypatch):
    """ScriptWriter est simulé : ce test vérifie l'orchestration du rapport
    (storyboard, prompts d'image, mise en forme), pas la qualité d'un
    script réel — c'est `pdz avant-apres` en conditions réelles qui sert à
    ça, avec de vraies vidéos privées."""
    u = Univers.charger(FRUITS)
    u.id = "reference-test"
    u.empreinte_creative = _empreinte_distincte("reference-test")
    perso_id = u.personnages[0].id
    (tmp_path / "reference-test.mp4").write_bytes(b"")
    u.sauver(tmp_path / "reference-test.univers.yaml")
    (tmp_path / "reference-test.yaml").write_text(
        "mecanique_attendue: pose une question jamais résolue\n"
        "sujet_original: une IA qui explique la physique quantique\n",
        encoding="utf-8",
    )

    async def _script_simule(self, entrees, ctx):
        return {
            "titre": "Le mystère de la pizza",
            "repliques": [
                {"numero": 1, "personnage": perso_id, "replique": "où est la pizza ?",
                 "action": "elle regarde la table", "emotion": "surprise", "decor": "",
                 "reaction_de": "", "relance": True, "fonction_plan": "établit l'enjeu"},
                {"numero": 2, "personnage": perso_id, "replique": "quelqu'un l'a prise",
                 "action": "elle fouille la cuisine", "emotion": "colere", "decor": "",
                 "reaction_de": "", "relance": False, "fonction_plan": "fait monter la tension"},
            ],
            "derniere_image": "boucle sur la table vide",
        }

    monkeypatch.setattr(script_module.ScriptWriter, "executer", _script_simule)

    avant_apres(reference="reference-test", sujet="une dispute pour une pizza",
               dossier=tmp_path, duree=45, sortie=None, verbeux=False)

    fichiers_rapport = list(tmp_path.glob("reference-test_avant_apres_*.md"))
    assert len(fichiers_rapport) == 1
    texte = fichiers_rapport[0].read_text(encoding="utf-8")
    assert "où est la pizza" in texte
    assert "établit l'enjeu" in texte
    assert "fait monter la tension" in texte
    assert "0 paire(s) consécutive(s) identique(s)" in texte
    assert "pose une question jamais résolue" in texte
    assert "une IA qui explique la physique quantique" in texte
    assert "SAME FUNCTION + NEW SUBJECT + NEW STORY + NEW VISUAL EXECUTION" in texte
