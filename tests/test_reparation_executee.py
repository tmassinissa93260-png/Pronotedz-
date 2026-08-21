"""La boucle de réparation : un diagnostic doit CHANGER ce qu'on renvoie.

Le dépôt savait déjà diagnostiquer (`pdz/diagnostics`) et savait déjà
choisir une réparation dans un catalogue (`pdz/repair`). Ce qui manquait
était le fil entre les deux et le rendu : un plan diagnostiqué
`STATIC_RENDER` repartait au repli local sans que personne n'ait essayé
la correction que le diagnostic venait pourtant de nommer.

Ce fichier vérifie les trois propriétés qui font la différence entre une
boucle de réparation et une simple relance :

  1. **la correction part vraiment chez le fournisseur** — le second appel
     ne porte pas le même prompt que le premier ;
  2. **la boucle est bornée** — par le nombre de tentatives ET par le
     budget, parce qu'une boucle non bornée est une machine à dépenser ;
  3. **une correction sans effet n'est jamais retentée** — c'est le
     garde-fou central : relancer à l'identique, c'est repayer pour un
     résultat déjà mesuré.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdz.backends import video as backend_video_mod
from pdz.backends.base import ArtefactRendu
from pdz.contracts import TypeReparation
from pdz.production import animation, verification_mouvement
from pdz.production.verification_mouvement import VerdictMouvement
from pdz.univers import Univers

FRUITS = Path(__file__).resolve().parent.parent / "univers" / "fruit-island.yaml"


class BackendEspion:
    """Un backend vidéo qui note ce qu'on lui demande et rend ce qu'on veut.

    Passe par `BACKENDS`, le registre PUBLIC — jamais par une porte privée.
    C'est précisément pour que les tests n'aient pas à forcer un `import`
    de fournisseur que ce registre a été rendu public.
    """

    nom = "fal"

    def __init__(self, cout=0.09):
        self.specs = []
        self.cout = cout

    def executer(self, spec):
        self.specs.append(spec)
        destination = Path(spec.parametres["destination"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"clip")
        return ArtefactRendu(fichier=destination, cout_eur=self.cout)


def _plan(**extra):
    base = {
        "numero": 1, "personnage": "", "action": "il parle",
        "emotion": "colere", "duree_s": 3.0, "decor": "",
        "intensite_mouvement": "moyen", "mouvement_camera": "travelling",
    }
    base.update(extra)
    return base


@pytest.fixture
def atelier_anime(tmp_path, monkeypatch):
    """Un plan, une image, un backend espion branché sur le registre."""
    espion = BackendEspion()
    monkeypatch.setitem(backend_video_mod.BACKENDS, "fal", espion)
    image = tmp_path / "plan_000.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0")
    return espion, image, tmp_path


def _verdicts(monkeypatch, suite):
    """Fait rendre à `verifier()` la suite de verdicts donnée, dans l'ordre."""
    restants = list(suite)
    def faux(chemin, *, fenetre_s=None):
        return restants.pop(0) if restants else suite[-1]
    monkeypatch.setattr(verification_mouvement, "verifier", faux)


STATIQUE = VerdictMouvement(fichier_valide=True, duree_s=4.8, fps=24.0,
                            frames_echantillonnees=8, diff_moyenne=0.4,
                            mouvement_detecte=False, raison="static_clip")
ANIME = VerdictMouvement(fichier_valide=True, duree_s=4.8, fps=24.0,
                         frames_echantillonnees=8, diff_moyenne=1.7,
                         mouvement_detecte=True, raison="ok")

# Le budget qui élit exactement UN plan, lu au lieu d'être deviné : le tarif
# vient de `modeles.yaml`, et le coder en dur ici ferait passer ce fichier au
# rouge le jour d'un changement de tarif — pour une raison sans rapport avec
# ce qu'il vérifie.
BUDGET_UN_PLAN = next(
    b / 100 for b in range(1, 500)
    if animation.combien_animer(1, b / 100, profil="equilibre",
                                duree_clip_s=5)[0] == 1
)


def _animer(plans, image, dossier, **kw):
    u = Univers.charger(FRUITS)
    # `equilibre` et non `economique` : le profil économique désactive
    # l'animation payante, donc aucun appel n'aurait lieu et ce fichier
    # ne testerait rien du tout.
    params = dict(budget_restant=5.0, profil="equilibre",
                  vie_pour_le_reste=False)
    params.update(kw)
    return animation.animer(plans, [image] * len(plans), u,
                            dossier / "anim", **params)


# ── 1. La correction part vraiment chez le fournisseur ─────────────────

def test_un_rendu_statique_est_retente_avec_un_prompt_different(
        atelier_anime, monkeypatch):
    """La propriété qui distingue une réparation d'une relance.

    Retenter à l'identique aurait produit deux appels au prompt IDENTIQUE
    — c'est-à-dire payer deux fois pour un résultat déjà mesuré. Ce que ce
    test exige, c'est que le second appel porte une CONSIGNE différente.
    """
    espion, image, tmp = atelier_anime
    _verdicts(monkeypatch, [STATIQUE, ANIME])

    resultats = _animer([_plan()], image, tmp)

    assert len(espion.specs) == 2, "le plan statique n'a pas été retenté"
    assert espion.specs[0].prompt != espion.specs[1].prompt, (
        "le second appel porte le même prompt que le premier : c'est une "
        "relance à l'identique, pas une réparation"
    )
    # Et la réparation a réussi : le plan sort animé par le modèle.
    assert resultats[0].anime
    assert resultats[0].methode == "modele"
    assert resultats[0].diagnostic == "mouvement_confirme"


def test_le_cout_rapporte_est_celui_de_toutes_les_tentatives(
        atelier_anime, monkeypatch):
    """Deux appels payants, c'est deux fois le prix — et ça doit se voir.

    Ne rapporter que la dernière tentative ferait mentir le budget d'un
    facteur égal au nombre de réparations, exactement dans le cas où la
    dépense mérite le plus d'être surveillée.
    """
    espion, image, tmp = atelier_anime
    _verdicts(monkeypatch, [STATIQUE, ANIME])

    resultats = _animer([_plan()], image, tmp)

    assert len(espion.specs) == 2
    assert resultats[0].cout == pytest.approx(2 * espion.cout)


# ── 2. La boucle est bornée ────────────────────────────────────────────

def test_la_boucle_sarrete_apres_deux_tentatives(atelier_anime, monkeypatch):
    """Un plan qui reste statique quoi qu'on fasse ne doit pas boucler.

    Trois appels au maximum : l'original plus deux réparations. Au-delà,
    on tombe au repli local, qui est gratuit.
    """
    espion, image, tmp = atelier_anime
    _verdicts(monkeypatch, [STATIQUE] * 10)

    resultats = _animer([_plan()], image, tmp)

    # Trois exactement : l'original, puis les deux corrections applicables
    # (amplifier le mouvement, verrouiller la caméra), que `deja_tentees`
    # empêche de répéter. Un quatrième appel voudrait dire que la boucle
    # retente une correction déjà essayée.
    assert len(espion.specs) == 3, (
        f"{len(espion.specs)} appels payants pour un seul plan : la boucle "
        "de réparation n'est pas bornée comme documenté"
    )
    assert not resultats[0].anime or resultats[0].methode != "modele"
    assert resultats[0].diagnostic == "rejete_mouvement"


def test_un_budget_epuise_interdit_la_reparation(atelier_anime, monkeypatch):
    """Réparer coûte le prix d'un rendu. Sans budget, pas de réparation.

    C'est la même règle que pour la génération initiale : le budget est un
    plafond réel, pas une intention. Un système qui répare gratuitement en
    théorie et facture en pratique est un système qui dépasse.
    """
    espion, image, tmp = atelier_anime
    _verdicts(monkeypatch, [STATIQUE] * 10)

    # Le rendu consomme EXACTEMENT le budget : il reste de quoi élire le
    # plan, et plus rien ensuite. C'est le seul réglage qui teste la borne
    # budgétaire de la réparation plutôt que celle de l'élection.
    espion.cout = BUDGET_UN_PLAN
    _animer([_plan()], image, tmp, budget_restant=BUDGET_UN_PLAN)

    assert len(espion.specs) == 1, (
        "une réparation a été lancée alors que le budget était épuisé"
    )


# ── 3. Une correction sans effet n'est jamais retentée ─────────────────

def test_une_camera_deja_fixe_ne_declenche_aucune_relance(
        atelier_anime, monkeypatch):
    """Le garde-fou central, vérifié de bout en bout.

    Sur un plan dont la caméra est DÉJÀ verrouillée, `AJUSTER_CAMERA` ne
    change rien : le plan corrigé serait identique au plan d'origine. Le
    relancer reviendrait à repayer pour un résultat déjà connu. La seule
    réparation qui reste applicable est l'amplification du mouvement, et
    elle ne peut être tentée qu'une fois avant de changer quelque chose.
    """
    espion, image, tmp = atelier_anime
    _verdicts(monkeypatch, [STATIQUE] * 10)

    plan = _plan(mouvement_camera="fixe", intensite_mouvement="fort")
    _animer([plan], image, tmp)

    # Rien à amplifier (déjà « fort »), rien à verrouiller (déjà « fixe ») :
    # aucune correction ne modifie ce plan, donc aucune relance.
    assert len(espion.specs) == 1, (
        "un plan sur lequel aucune correction n'a d'effet a quand même été "
        "relancé : c'est une relance à l'identique déguisée en réparation"
    )


# ── 4. L'unité : _reparer décline ce qui ne le concerne pas ────────────

def test_reparer_refuse_un_diagnostic_non_actionnable():
    """Un diagnostic peu sûr ne justifie pas de redépenser.

    `actionnable` est la porte : un diagnostic dont la confiance est trop
    basse décrit une hypothèse, pas une cause. Agir dessus reviendrait à
    transformer une incertitude en dépense.
    """
    class DiagnosticMou:
        actionnable = False

    corrige, reparation, _ = animation._reparer(
        DiagnosticMou(), _plan(), tentative=0, deja_tentees=(),
        budget_restant=5.0)
    assert corrige is None
    assert reparation is None


def test_reparer_refuse_quand_il_ny_a_plus_de_budget():
    corrige, _, _ = animation._reparer(
        None, _plan(), tentative=0, deja_tentees=(), budget_restant=0.0)
    assert corrige is None


def test_seules_les_reparations_de_mouvement_sont_applicables_ici():
    """`animer()` ne sait corriger que le mouvement et la caméra.

    Le catalogue de réparations couvre d'autres étages (changer de
    stratégie, redécouper un plan, régénérer l'image de départ). Les
    accepter en silence ici produirait un plan corrigé que ce module ne
    sait pas appliquer. La liste est donc explicite, et ce test la garde
    alignée sur ce que `_CORRECTIONS` sait réellement faire.
    """
    assert set(animation._REPARATIONS_APPLICABLES) == set(animation._CORRECTIONS)
    for type_reparation in animation._REPARATIONS_APPLICABLES:
        assert isinstance(type_reparation, TypeReparation)
