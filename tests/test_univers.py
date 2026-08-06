"""L'univers ne connaît aucune niche.

Ces tests vérifient la promesse centrale : fruits, voitures et anime passent
par exactement le même code. Si un jour quelqu'un code une niche en dur,
c'est ici que ça se verra.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from pdz.univers import Format, Style, Univers

UNIVERS = sorted(Path("univers").glob("*.yaml"))


@pytest.mark.parametrize("chemin", UNIVERS, ids=lambda p: p.stem)
def test_chaque_univers_se_charge(chemin):
    u = Univers.charger(chemin)
    assert u.personnages, "un univers sans personnage n'a pas de sens"
    assert u.style.rendu
    for p in u.personnages:
        assert p.apparence, f"{p.nom} n'a pas de description visuelle"
        assert p.espece


def test_les_trois_niches_partagent_le_meme_code():
    """Fruit, voiture et anime : même modèle, même méthode, même sortie."""
    univers = [Univers.charger(c) for c in UNIVERS]
    especes = {u.id: u.personnages[0].espece for u in univers}

    assert "fraise" in especes["fruit-island"]
    assert "Renault" in especes["garage-42"]
    assert "bretteur" in especes["shonen-90s"]

    # Le même appel produit un prompt valide dans les trois cas.
    for u in univers:
        prompt = u.personnages[0].prompt_image("looking at the camera", u.style)
        assert u.personnages[0].apparence.split(",")[0].strip() in prompt
        assert u.style.rendu.split(",")[0].strip() in prompt


def test_le_contexte_script_contient_tout_le_casting():
    u = Univers.charger(Path("univers/fruit-island.yaml"))
    ctx = u.contexte_script()
    for p in u.personnages:
        assert p.nom in ctx
        assert p.caractere in ctx
    assert "RÈGLES DU MONDE" in ctx
    assert "INTERDITS" in ctx


@pytest.mark.parametrize(
    "rendu",
    ["in the style of Naruto", "Dragon Ball inspired art", "like a Disney movie"],
)
def test_les_oeuvres_protegees_sont_bloquees(rendu):
    with pytest.raises(ValidationError) as exc:
        Style(rendu=rendu)
    assert "protégé" in str(exc.value)


def test_un_style_decrit_par_ses_caracteristiques_passe():
    """La formulation correcte : décrire, pas référencer."""
    s = Style(rendu="90s cel-shaded anime, thick ink outlines, visible film grain")
    assert s.rendu


def test_aller_retour_yaml(tmp_path):
    origine = Univers.charger(Path("univers/garage-42.yaml"))
    copie = tmp_path / "copie.yaml"
    origine.sauver(copie)
    assert Univers.charger(copie).model_dump() == origine.model_dump()


def test_format_par_defaut_et_variantes():
    u = Univers.charger(Path("univers/fruit-island.yaml"))
    assert u.format is Format.SERIE_ANIMEE
    assert u.anime is True
