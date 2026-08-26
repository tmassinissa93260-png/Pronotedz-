"""Le workflow appelle-t-il la CLI avec des options qui existent ?

Le run #9 est mort en deux secondes sur `pdz2: error: unrecognized arguments:
--animated-shots 0`. L'option avait bien été ajoutée — à la sous-commande
`research`, alors que le workflow appelle `pdz2 create`, qui enchaîne les
phases et possède son propre analyseur.

Rien dans la suite ne pouvait l'attraper : les tests exercent les fonctions,
le workflow exerce la ligne de commande, et personne ne vérifiait que les deux
parlaient de la même chose. C'est un défaut de couture, et une couture non
testée finit par lâcher — celle-ci a coûté un aller-retour complet, fusion
comprise.

Ces tests lisent le vrai fichier de workflow et confrontent chaque invocation
à l'analyseur réel. Aucune commande n'est exécutée : on ne teste que
l'acceptation des arguments.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/pdz2.yml"


def _defauts_des_entrees() -> dict[str, object]:
    """Les valeurs que GitHub passera si personne ne touche au formulaire."""
    import yaml

    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # `on:` est lu comme le booléen True par YAML 1.1 — la clé peut être l'un
    # ou l'autre selon l'analyseur, on prend celle qui est là.
    declencheurs = document.get("on", document.get(True, {}))
    entrees = declencheurs["workflow_dispatch"]["inputs"]
    return {nom: champ.get("default", "") for nom, champ in entrees.items()}

# `pdz2 <sous-commande> …`, jusqu'à la fin de la commande shell — les
# continuations de ligne par antislash sont recollées avant l'analyse.
_APPEL = re.compile(r"\bpdz2\s+([a-z][a-z-]*)\b([^\n|;&]*)")


def _invocations() -> list[tuple[str, list[str]]]:
    """Chaque appel à `pdz2` trouvé dans le workflow, découpé en arguments.

    Les expressions `${{ inputs.x }}` sont remplacées par la **valeur par
    défaut déclarée pour cette entrée**, pas par un mot quelconque : c'est ce
    que GitHub passera si personne ne touche au formulaire, et ça vérifie du
    même coup que le type concorde — un `duree` par défaut qui ne serait pas
    un nombre ferait échouer `--duration` exactement comme en production.
    """
    texte = WORKFLOW.read_text(encoding="utf-8")
    texte = texte.replace("\\\n", " ")
    defauts = _defauts_des_entrees()

    def _valeur(correspondance: re.Match[str]) -> str:
        nom = correspondance.group(1)
        if nom not in defauts:
            raise AssertionError(
                f"le workflow emploie `inputs.{nom}`, qui n'est pas déclarée"
            )
        return str(defauts[nom])

    texte = re.sub(r"\$\{\{\s*inputs\.([a-zA-Z_][\w-]*)\s*\}\}", _valeur, texte)
    texte = re.sub(r"\$\{\{[^}]*\}\}", "valeur", texte)
    trouves = []
    for commande, reste in _APPEL.findall(texte):
        try:
            arguments = shlex.split(reste)
        except ValueError:  # guillemet non fermé dans un fragment de YAML
            continue
        trouves.append((commande, arguments))
    return trouves


def test_the_workflow_actually_calls_the_cli() -> None:
    """Sans ça, les tests suivants passeraient en ne vérifiant rien."""
    assert WORKFLOW.is_file(), f"workflow introuvable : {WORKFLOW}"
    appels = _invocations()
    assert appels, "aucun appel à pdz2 trouvé dans le workflow"
    assert any(commande == "create" for commande, _ in appels), (
        "le workflow n'appelle plus `pdz2 create` : ce test vise à côté"
    )


@pytest.mark.parametrize("commande, arguments", _invocations())
def test_every_option_the_workflow_uses_exists(commande, arguments) -> None:
    from pdz2.cli.main import build_parser

    parser = build_parser()
    sous = parser._subparsers._group_actions[0].choices  # noqa: SLF001
    if commande not in sous:
        pytest.fail(
            f"le workflow appelle `pdz2 {commande}`, que la CLI ne connaît pas"
        )
    connues = {
        chaine
        for action in sous[commande]._actions  # noqa: SLF001
        for chaine in action.option_strings
    }
    for argument in arguments:
        if not argument.startswith("--"):
            continue
        nom = argument.split("=", 1)[0]
        assert nom in connues, (
            f"`pdz2 {commande} {nom}` : option inconnue de l'analyseur — "
            "le workflow échouera au démarrage, comme au run #9"
        )


def test_the_end_to_end_command_parses_as_written() -> None:
    """L'invocation de `create` doit franchir l'analyseur telle quelle.

    C'est le test qui aurait épargné le run #9 : il ne regarde pas les options
    une par une, il donne la ligne entière à `parse_args`.
    """
    from pdz2.cli.main import build_parser

    appels = [a for a in _invocations() if a[0] == "create"]
    assert appels
    for _, arguments in appels:
        build_parser().parse_args(["create", *arguments])
