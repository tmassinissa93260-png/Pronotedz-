"""Le diagnostic de diversité des empreintes créatives.

La diversité n'est pas une contrainte : dix vidéos qui partagent réellement
le même mécanisme, ce n'est pas une erreur à corriger de force. C'est un
signal — « regarde de plus près » — jamais une note à faire remonter à tout
prix. Voir pdz/analyse/diversite.py.
"""

from __future__ import annotations

from pdz.analyse.diversite import MINIMUM_POUR_DIAGNOSTIC, diagnostic_diversite
from pdz.univers import ChampInterprete, EmpreinteCreative, EmpreinteHook


def _empreinte(hook_type="question impossible", confiance=0.8):
    return EmpreinteCreative(
        hook=EmpreinteHook(type=ChampInterprete(valeur=hook_type, confiance=confiance)),
    )


def test_sous_le_minimum_aucune_alerte():
    """Deux vidéos qui partagent un hook, c'est un hasard, pas un signal."""
    empreintes = [(f"v{i}", _empreinte()) for i in range(MINIMUM_POUR_DIAGNOSTIC - 1)]
    assert diagnostic_diversite(empreintes) == []


def test_une_repetition_marquee_est_signalee():
    empreintes = [(f"v{i}", _empreinte("question impossible")) for i in range(8)]
    empreintes += [(f"v{i}", _empreinte("démonstration")) for i in range(8, 10)]
    alertes = diagnostic_diversite(empreintes)
    assert any(a.champ == "hook.type" for a in alertes)
    trouvee = next(a for a in alertes if a.champ == "hook.type")
    assert trouvee.valeur_dominante == "question impossible"
    assert trouvee.occurrences == 8
    assert trouvee.total == 10


def test_une_vraie_diversite_ne_declenche_rien():
    empreintes = [
        (f"v{i}", _empreinte(hook))
        for i, hook in enumerate([
            "question impossible", "démonstration", "affirmation choquante",
            "paradoxe", "révélation immédiate",
        ])
    ]
    assert diagnostic_diversite(empreintes) == []


def test_les_unknown_ne_comptent_jamais_comme_une_repetition():
    """Dix vidéos où le modèle n'a pas su trancher ne prouvent aucune
    répétition — seulement dix incertitudes."""
    empreintes = [(f"v{i}", _empreinte("unknown", confiance=0.0)) for i in range(10)]
    assert diagnostic_diversite(empreintes) == []


def test_le_message_nomme_le_champ_et_la_part():
    empreintes = [(f"v{i}", _empreinte("question impossible")) for i in range(5)]
    alerte = diagnostic_diversite(empreintes)[0]
    texte = str(alerte)
    assert "POTENTIAL_ANALYSIS_COLLAPSE" in texte
    assert "hook.type" in texte
    assert "5/5" in texte


def test_juste_sous_le_seuil_ne_declenche_rien():
    """0,7 est le seuil : en dessous, ce n'est pas encore un signal."""
    empreintes = [(f"v{i}", _empreinte("question impossible")) for i in range(6)]
    empreintes += [(f"v{i}", _empreinte(f"autre_{i}")) for i in range(6, 10)]
    # 6/10 = 60 % < 70 %
    assert diagnostic_diversite(empreintes) == []
