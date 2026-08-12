"""Le décor porté d'une réplique à l'autre, et les scènes qui en découlent.

Aucun appel IA : deux règles mécaniques appliquées à ce que le scénariste a
déjà écrit.
"""

from __future__ import annotations

from pdz.production import continuite


def _repliques(*decors):
    return [{"numero": i + 1, "decor": d} for i, d in enumerate(decors)]


def test_un_decor_precise_reste_inchange():
    repliques = _repliques("villa", "ceremonie")
    portees = continuite.porter_le_decor(repliques)
    assert [r["decor"] for r in portees] == ["villa", "ceremonie"]


def test_un_decor_vide_herite_du_precedent():
    repliques = _repliques("villa", "", "")
    portees = continuite.porter_le_decor(repliques)
    assert [r["decor"] for r in portees] == ["villa", "villa", "villa"]


def test_un_decor_vide_en_debut_depisode_reste_vide():
    """Rien à hériter avant la première réplique."""
    repliques = _repliques("", "villa")
    portees = continuite.porter_le_decor(repliques)
    assert portees[0]["decor"] == ""
    assert portees[1]["decor"] == "villa"


def test_un_nouveau_decor_explicite_reprend_la_main():
    repliques = _repliques("villa", "", "ceremonie", "")
    portees = continuite.porter_le_decor(repliques)
    assert [r["decor"] for r in portees] == ["villa", "villa", "ceremonie", "ceremonie"]


def test_porter_le_decor_ne_mute_pas_les_repliques_dorigine():
    repliques = _repliques("villa", "")
    continuite.porter_le_decor(repliques)
    assert repliques[1]["decor"] == ""


def test_porter_le_decor_ne_touche_pas_aux_autres_champs():
    repliques = [{"numero": 1, "decor": "villa", "replique": "salut", "emotion": "calme"}]
    portees = continuite.porter_le_decor(repliques)
    assert portees[0]["replique"] == "salut"
    assert portees[0]["emotion"] == "calme"


# ── Scènes déduites des décors ───────────────────────────────────────────

def test_un_decor_stable_donne_une_seule_scene():
    assert continuite.indices_de_scene(["villa", "villa", "villa"]) == [0, 0, 0]


def test_un_changement_de_decor_ouvre_une_nouvelle_scene():
    indices = continuite.indices_de_scene(["villa", "villa", "ceremonie", "ceremonie"])
    assert indices == [0, 0, 1, 1]


def test_chaque_decor_different_ouvre_sa_propre_scene():
    indices = continuite.indices_de_scene(["a", "b", "c"])
    assert indices == [0, 1, 2]


def test_une_liste_vide_ne_plante_pas():
    assert continuite.indices_de_scene([]) == []
