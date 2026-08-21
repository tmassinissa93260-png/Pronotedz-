"""Le dossier des références : un seul lecteur de l'environnement.

`pdz/config.py` promet en toutes lettres être le seul endroit du projet qui
lit l'environnement. `pdz/analyse/references.py` lisait pourtant
`PDZ_DOSSIER_REFERENCES` en direct — donc ce réglage n'existait dans aucun
champ de `Config`, et ni `pdz cles`, ni `.env.exemple`, ni la documentation
ne pouvaient le connaître. Un réglage invisible pour l'outillage.

Ce fichier verrouille les trois propriétés du rapatriement : le nom
historique de la variable continue de marcher, le défaut est inchangé, et
une valeur VIDE ne veut pas dire « la racine du dépôt ».
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdz.analyse.references import dossier_references
from pdz.config import Config, config

DEFAUT = Path("donnees/references")


@pytest.fixture(autouse=True)
def _env_propre(monkeypatch):
    monkeypatch.delenv("PDZ_DOSSIER_REFERENCES", raising=False)
    config.cache_clear()
    yield
    config.cache_clear()


def test_le_reglage_existe_dans_config():
    """C'était tout le problème : il n'y était pas.

    Un réglage absent de `Config` est un réglage que `pdz cles` ne liste
    pas, que `.env.exemple` ne mentionne pas, et dont personne ne peut
    deviner l'existence sans lire le code du module qui s'en sert.
    """
    assert "dossier_references" in Config.model_fields


def test_le_defaut_est_inchange():
    assert Config().dossier_references == DEFAUT


def test_le_nom_historique_de_la_variable_marche_toujours(monkeypatch):
    """pydantic-settings aurait dérivé `DOSSIER_REFERENCES` du nom du champ.

    Accepter ce nom-là aurait cassé les installations qui utilisent
    `PDZ_DOSSIER_REFERENCES` depuis toujours — pour le seul bénéfice d'une
    cohérence de préfixe. D'où le `validation_alias`.
    """
    monkeypatch.setenv("PDZ_DOSSIER_REFERENCES", "/mnt/disque/refs")
    assert Config().dossier_references == Path("/mnt/disque/refs")


@pytest.mark.parametrize("valeur", ["", "   ", "\t"])
def test_une_variable_vide_ne_veut_pas_dire_la_racine(monkeypatch, valeur):
    """Le piège que `.env.exemple` posait.

    `PDZ_DOSSIER_REFERENCES=` donne la chaîne vide, que `Path` transforme
    en `Path(".")` — le dépôt entier. Quelqu'un qui copie le fichier
    d'exemple verrait `pdz references` parcourir tout le projet au lieu du
    dossier prévu, sans un mot d'avertissement. Vide veut dire « je n'ai
    rien choisi », donc le défaut.
    """
    monkeypatch.setenv("PDZ_DOSSIER_REFERENCES", valeur)
    assert Config().dossier_references == DEFAUT


def test_la_fonction_du_module_suit_config(monkeypatch):
    """`dossier_references()` ne lit plus l'environnement : elle lit config().

    C'est la propriété que le test d'architecture garde côté statique ;
    celle-ci la vérifie côté comportement, ce qu'une règle sur l'AST ne
    peut pas faire.
    """
    monkeypatch.setenv("PDZ_DOSSIER_REFERENCES", "/mnt/ailleurs")
    config.cache_clear()
    assert dossier_references() == Path("/mnt/ailleurs")


def test_le_fichier_dexemple_laisse_le_reglage_commente():
    """Une ligne non commentée dans `.env.exemple` est un piège armé.

    Le fichier est fait pour être copié tel quel. Une valeur vide y
    écraserait le défaut par la racine du dépôt — c'est précisément ce que
    le validateur rattrape, mais mieux vaut ne pas armer le piège.
    """
    exemple = (Path(__file__).resolve().parent.parent / ".env.exemple"
               ).read_text(encoding="utf-8")
    actives = [ligne for ligne in exemple.splitlines()
               if ligne.strip().startswith("PDZ_DOSSIER_REFERENCES")]
    assert not actives, f"ligne active dans .env.exemple : {actives}"
    assert "PDZ_DOSSIER_REFERENCES" in exemple, (
        "le réglage a disparu du fichier d'exemple : il redevient invisible"
    )
