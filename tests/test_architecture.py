"""Les frontières d'import du compilateur, vérifiées mécaniquement.

Une règle d'architecture qui vit dans un document est une intention ; une
règle vérifiée par un test est une garantie. Ce fichier ne contient donc
aucune logique métier — il lit les `import` du paquet `pdz` et vérifie que
les dépendances vont toujours dans le même sens.

La règle, du plus abstrait au plus concret (voir
docs/TARGET_ARCHITECTURE.md § 2) :

    contracts          ← n'importe rien du reste de pdz
        ↑
    domaine            ← contracts, kernel      (JAMAIS un fournisseur)
        ↑
    compilateur / stratégies
        ↑
    backends           ← contracts, capacités   (JAMAIS le domaine)
        ↑
    infrastructure

Le point qui compte le plus, et le seul qui échoue aujourd'hui :

    LE DOMAINE NE CONNAÎT AUCUN FOURNISSEUR.

Un module de production n'a pas à savoir que fal.ai existe. Il demande une
capacité, le registre résout, un adaptateur exécute. `production/animation.py`
viole cette règle — il importe `pdz.ia.fal` en direct. C'est un écart CONNU,
daté et déclaré ci-dessous (`ECARTS_CONNUS`) : le test le verrouille pour
qu'il ne s'en ajoute pas un second, et échouera le jour où il sera réparé,
ce qui obligera à retirer la dérogation plutôt qu'à l'oublier.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
PAQUET = RACINE / "pdz"

# ── Les fournisseurs concrets : ce que le domaine n'a pas le droit de citer ──
#
# `pdz.ia.registre` et `pdz.ia.texte`/`pdz.ia.images` n'en font PAS partie :
# ce sont les points d'entrée qui existent précisément pour que le domaine
# n'ait pas à choisir. Seuls les adaptateurs d'un fournisseur nommé sont
# interdits.
ADAPTATEURS_FOURNISSEUR = {
    "pdz.ia.claude", "pdz.ia.groq", "pdz.ia.fal", "pdz.ia.pollinations",
    "pdz.ia.elevenlabs", "pdz.ia.audd",
}

# Le domaine : ce qui décide QUOI produire, jamais AVEC QUOI.
# `director`, `narrative` et `research` s'y ajoutent dès leur création : une
# couche neuve qui échapperait à la règle la rendrait décorative.
DOMAINE = ("production", "univers", "agents", "analyse",
           "director", "narrative", "research",
           "observation", "diagnostics", "repair", "strategies",
           "renderability", "execution", "memory", "world", "scenes")

# ── Écarts connus, datés, et destinés à disparaître ──────────────────────
#
# Chaque entrée est une dette déclarée, pas une permission. Retirer la ligne
# est la dernière étape de sa réparation — le test échouera si la violation
# persiste, et échouera AUSSI si elle disparaît sans qu'on retire la ligne.
ECARTS_CONNUS: dict[str, str] = {
    # Vide, et c'est un résultat : les quatre écarts relevés en PHASE 1
    # (animation→fal, voix→elevenlabs, appariement_voix→elevenlabs,
    # musique→audd) ont été réparés en PHASE 6. Le métier passe désormais
    # par `pdz/backends/`, qui enveloppe les clients HTTP sans les réécrire.
    #
    # Laisser le dictionnaire en place plutôt que le supprimer : la prochaine
    # dette de ce type aura un endroit évident où être DÉCLARÉE, datée et
    # verrouillée, au lieu d'être découverte six mois plus tard.
}

# ── Lecture directe de l'environnement, hors pdz/config.py ──────────────
#
# `config.py` promet en toutes lettres : « Rien d'autre dans le projet ne lit
# os.environ. » C'était faux, et personne ne pouvait le savoir — rien ne le
# vérifiait. `PDZ_DOSSIER_REFERENCES` n'existe dans aucun champ de `Config`,
# donc ni `pdz cles`, ni `.env.exemple`, ni la documentation ne le mentionnent.
# Non corrigé ici : la PHASE 1 n'a pas le droit de toucher au comportement, et
# déplacer ce réglage suppose de choisir comment préserver le nom de la
# variable (pydantic-settings dériverait `DOSSIER_REFERENCES`, pas
# `PDZ_DOSSIER_REFERENCES`). Déclaré, daté, à traiter avec les contrats.
LECTEURS_ENV_CONNUS: dict[str, str] = {
    "pdz/analyse/references.py":
        "lit PDZ_DOSSIER_REFERENCES, absent de Config. À rapatrier en PHASE 2.",
}


def _modules() -> list[pathlib.Path]:
    return sorted(p for p in PAQUET.rglob("*.py") if "__pycache__" not in p.parts)


def _imports(fichier: pathlib.Path) -> set[str]:
    """Tous les modules `pdz.*` importés par ce fichier, y compris ceux
    importés dans le corps d'une fonction — un import différé reste un
    couplage, et c'est exactement là que se cachent les violations."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"), filename=str(fichier))
    trouves: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            trouves.update(a.name for a in noeud.names if a.name.startswith("pdz"))
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            if not noeud.module.startswith("pdz"):
                continue
            trouves.add(noeud.module)
            # `from pdz.ia import fal` désigne bien pdz.ia.fal.
            trouves.update(f"{noeud.module}.{a.name}" for a in noeud.names)
    return trouves


def _relatif(fichier: pathlib.Path) -> str:
    return fichier.relative_to(RACINE).as_posix()


# ── La règle qui compte : le domaine ignore les fournisseurs ────────────

def test_le_domaine_ne_connait_aucun_fournisseur():
    violations: dict[str, set[str]] = {}

    for fichier in _modules():
        chemin = _relatif(fichier)
        if fichier.relative_to(PAQUET).parts[0] not in DOMAINE:
            continue
        if (fautifs := _imports(fichier) & ADAPTATEURS_FOURNISSEUR):
            violations[chemin] = fautifs

    nouvelles = {c: v for c, v in violations.items() if c not in ECARTS_CONNUS}
    assert not nouvelles, (
        "Un module du domaine importe un fournisseur en direct :\n"
        + "\n".join(f"  {c} → {', '.join(sorted(v))}" for c, v in sorted(nouvelles.items()))
        + "\n\nLe domaine demande une CAPACITÉ (pdz.ia.texte / pdz.ia.images), "
          "il ne choisit jamais un fournisseur. Voir docs/TARGET_ARCHITECTURE.md § 2."
    )


@pytest.mark.parametrize("chemin", sorted(ECARTS_CONNUS))
def test_un_ecart_connu_reste_present_ou_sa_derogation_est_retiree(chemin):
    """Une dérogation obsolète est un mensonge sur l'état du dépôt.

    Ce test échoue dans les DEUX sens : si l'écart s'aggrave, la règle
    ci-dessus le dit ; s'il est réparé sans qu'on retire la ligne, celui-ci
    le dit. Une dette déclarée ne peut donc ni grossir, ni survivre en
    silence à sa propre réparation.
    """
    fichier = RACINE / chemin
    assert fichier.exists(), f"{chemin} a disparu : retire son entrée d'ECARTS_CONNUS."
    assert _imports(fichier) & ADAPTATEURS_FOURNISSEUR, (
        f"{chemin} n'importe plus aucun fournisseur — l'écart est réparé.\n"
        f"Retire son entrée d'ECARTS_CONNUS pour que la règle le protège vraiment."
    )


# ── Les contrats sont la source de vérité : ils ne dépendent de personne ──

def test_les_contrats_ne_dependent_de_rien():
    """`pdz/contracts/` n'existe pas encore (PHASE 2). Quand il existera, il
    ne devra importer aucun autre sous-paquet de `pdz` : un contrat qui
    dépend d'un module de production n'est plus une source de vérité, c'est
    une vue sur du code."""
    contrats = PAQUET / "contracts"
    if not contrats.is_dir():
        pytest.skip("pdz/contracts/ n'existe pas encore — voir PHASE 2")

    autorises = {"pdz", "pdz.contracts"}
    for fichier in sorted(contrats.rglob("*.py")):
        for importe in _imports(fichier):
            racine = ".".join(importe.split(".")[:2])
            assert racine in autorises, (
                f"{_relatif(fichier)} importe {importe} : un contrat ne "
                f"dépend d'aucune autre couche."
            )


# ── Une seule autorité sur la reprise ───────────────────────────────────

def test_seul_le_journal_ecrit_les_points_de_reprise():
    """Le GAP structurel principal du dépôt, verrouillé.

    `moteur/pipeline.py` et `production/episode.py` écrivaient chacun dans la
    table `etapes` sans se connaître. Deux mécanismes de reprise devant
    rester d'accord pour toujours — ce qui n'arrive jamais — et le chemin
    réel de production, `episode.py`, n'avait aucun accès au cache du moteur.

    `pdz/moteur/journal.py` est désormais le seul module autorisé à écrire
    dans `etapes` et `cache`. Un troisième mécanisme ne peut plus naître en
    silence : il faudrait ajouter son fichier ici, ce qui se voit en revue.
    """
    autorises = {"pdz/moteur/journal.py"}
    coupables = []

    for fichier in _modules():
        chemin = _relatif(fichier)
        if chemin in autorises:
            continue
        source = fichier.read_text(encoding="utf-8")
        for motif in ("INSERT INTO etapes", "UPDATE etapes",
                      "INSERT INTO cache", "INSERT OR REPLACE INTO cache"):
            if motif in source:
                coupables.append(f"{chemin} — « {motif} »")

    assert not coupables, (
        "Ces modules écrivent un point de reprise hors du journal :\n  "
        + "\n  ".join(coupables)
        + "\n\nUne seule autorité écrit dans `etapes` et `cache` : "
          "pdz/moteur/journal.py. Voir docs/MIGRATION_PLAN.md PHASE 5."
    )


# ── Le noyau ne remonte jamais vers le métier ───────────────────────────

def test_le_noyau_ignore_le_metier():
    """`pdz/moteur/` orchestre sans savoir ce qu'il orchestre. S'il importait
    `production`, il n'y aurait plus de moteur générique — seulement de la
    production déguisée."""
    interdits = {"pdz.production", "pdz.agents", "pdz.video", "pdz.analyse"}
    for fichier in sorted((PAQUET / "moteur").rglob("*.py")):
        if (fautifs := {i for i in _imports(fichier)
                        if ".".join(i.split(".")[:2]) in interdits}):
            pytest.fail(
                f"{_relatif(fichier)} importe {', '.join(sorted(fautifs))} : "
                "le noyau ne connaît pas le métier."
            )


# ── Les couches neuves ne dépendent que des contrats ────────────────────

def test_les_couches_de_decision_ne_dependent_que_des_contrats():
    """`director/`, `narrative/` et `research/` décident QUOI raconter.

    Elles ont le droit de connaître les contrats et l'univers (la matière
    d'entrée), jamais le moteur, la production ou le montage : une couche de
    décision qui connaîtrait l'exécution ne serait plus remplaçable, et le
    sens de la dépendance s'inverserait.

    `diagnostics/` et `repair/` en font partie, et c'est ce qui garantit
    qu'ils raisonnent sur des CONTRATS : un diagnostic qui relirait le
    `MotionProgram` depuis la production vivrait dans la couche de décision,
    et l'écart attendu/observé deviendrait invérifiable de l'extérieur.

    `observation/` et `renderability/` en sont exclues volontairement : elles
    APPELLENT les sondes et les filtres de `production/`, ce qui est leur
    rôle — traduire ce qui existe, sans le réimplémenter. `execution/` aussi :
    elle appelle le journal, et c'est précisément ce qu'on veut (une seule
    autorité sur la reprise, pas une troisième).
    """
    for couche in ("director", "narrative", "research", "diagnostics",
                   "repair", "world"):
        dossier = PAQUET / couche
        if not dossier.is_dir():
            continue
        # Une couche a évidemment le droit de s'importer elle-même : c'est
        # une organisation interne, pas une dépendance sortante.
        autorises = {"pdz", "pdz.contracts", "pdz.univers", f"pdz.{couche}"}
        for fichier in sorted(dossier.rglob("*.py")):
            for importe in _imports(fichier):
                racine = ".".join(importe.split(".")[:2])
                assert racine in autorises, (
                    f"{_relatif(fichier)} importe {importe} : une couche de "
                    f"décision ne connaît ni le moteur, ni la production."
                )


# ── Aucun module ne lit l'environnement hors de config.py ───────────────

def test_seul_config_lit_l_environnement():
    """`pdz/config.py` le promet en toutes lettres : « Rien d'autre dans le
    projet ne lit os.environ. » Une promesse en docstring est une intention ;
    ici elle devient une garantie."""
    coupables = []
    for fichier in _modules():
        if fichier.name == "config.py":
            continue
        source = fichier.read_text(encoding="utf-8")
        if "os.environ" in source or "os.getenv" in source:
            coupables.append(_relatif(fichier))

    nouveaux = [c for c in coupables if c not in LECTEURS_ENV_CONNUS]
    assert not nouveaux, (
        "Ces modules lisent l'environnement hors de pdz/config.py :\n  "
        + "\n  ".join(nouveaux)
        + "\nUn seul endroit lit la configuration, sinon elle devient imprévisible."
    )


@pytest.mark.parametrize("chemin", sorted(LECTEURS_ENV_CONNUS))
def test_un_lecteur_env_connu_reste_present_ou_sa_derogation_est_retiree(chemin):
    """Même verrou à double sens que pour les fournisseurs."""
    fichier = RACINE / chemin
    assert fichier.exists(), f"{chemin} a disparu : retire son entrée."
    source = fichier.read_text(encoding="utf-8")
    assert "os.environ" in source or "os.getenv" in source, (
        f"{chemin} ne lit plus l'environnement — retire son entrée de "
        f"LECTEURS_ENV_CONNUS pour que la règle le protège vraiment."
    )
