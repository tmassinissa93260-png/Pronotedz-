"""Les images passent par l'ordonnanceur : reprise par PLAN, et ordre gardé.

`episode.py` journalisait les images comme UNE étape. Un job interrompu au
plan 20 sur 26 repayait les vingt premiers — la reprise existait, mais sa
granularité était celle de l'étape, pas celle de la dépense. Chaque plan
est maintenant un nœud du DAG, journalisé séparément.

Ce fichier protège les trois propriétés qui rendent ce branchement utile
plutôt que décoratif :

  1. **la reprise est par plan** — relancer ne repaie que ce qui manque ;
  2. **l'ordre est celui du storyboard**, jamais celui d'arrivée des
     réponses — le montage zippe position par position, et une planche
     triée par latence produirait un épisode mélangé sans qu'aucun test de
     comptage ne le remarque ;
  3. **le plafond arrête la dépense** — un DAG qui parallélise sans borne
     budgétaire est une régression, pas une optimisation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pdz import db
from pdz.moteur.erreurs import ErreurBudget
from pdz.production import images
from pdz.production.storyboard import PlanScript
from pdz.univers import Univers
from tests.test_execution_dag import base  # noqa: F401 — fixture réutilisée

FRUITS = Path(__file__).resolve().parent.parent / "univers" / "fruit-island.yaml"


@pytest.fixture
def atelier(base, monkeypatch, tmp_path):  # noqa: F811
    """Un univers réel, des fiches gratuites, un générateur d'images espion.

    Les fiches de personnages sont neutralisées : elles sont produites
    AVANT le DAG et ne font pas partie de ce qu'on vérifie ici. Les laisser
    tourner ferait payer trois images à chaque test pour rien.
    """
    u = Univers.charger(FRUITS)
    monkeypatch.setattr(images, "fiches", lambda *a, **k: {})

    appels = []

    def faux_produire(prompt, destination, **k):
        appels.append(destination.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 2000)
        return 0.02, False

    monkeypatch.setattr(images, "_produire", faux_produire)
    return u, appels, tmp_path


def _plans(u, n=4):
    perso = u.personnages[0].id
    return [PlanScript(numero=i, replique_numero=i, personnage=perso,
                       action="il parle", emotion="calme", duree_s=3.0)
            for i in range(n)]


def _fabriquer(u, plans, dossier, **kw):
    params = dict(budget_max=5.0, cache=False, job_id="job_1")
    params.update(kw)
    return asyncio.run(images.fabriquer_dag(plans, u, dossier, **params))


# ── 1. La reprise est par plan ─────────────────────────────────────────

def test_relancer_ne_repaie_que_les_plans_manquants(atelier):
    """La propriété qui justifie tout ce branchement.

    Premier passage : quatre plans, quatre appels. Second passage sur le
    MÊME job : zéro appel, parce que le journal sait que les quatre nœuds
    sont faits — et le coût rapporté est celui du journal, pas zéro.
    """
    u, appels, tmp = atelier
    plans = _plans(u, 4)

    premiere = _fabriquer(u, plans, tmp / "img")
    assert len(appels) == 4
    assert premiere.cout == pytest.approx(4 * 0.02)

    appels.clear()
    seconde = _fabriquer(u, plans, tmp / "img")
    assert appels == [], "un plan déjà journalisé a été repayé"
    assert len(seconde.plans) == 4

    # `cout` est ce que CETTE exécution a dépensé, pas le prix historique
    # de la planche. Une reprise ne dépense rien, donc zéro — c'est la
    # sémantique que `episode.py` attend, puisqu'il compare ce nombre au
    # plafond du jour. Y remettre le coût d'origine rapprocherait le
    # plafond à chaque relance jusqu'à interdire une reprise gratuite.
    assert seconde.cout == 0.0
    assert seconde.images_evitees == 4

    # Le coût d'ORIGINE reste lisible plan par plan : c'est de la
    # provenance, et la perdre empêcherait de savoir ce que l'épisode a
    # coûté en tout, toutes exécutions confondues.
    assert sum(p.cout for p in seconde.plans) == pytest.approx(4 * 0.02)


def test_une_reprise_partielle_ne_refait_que_ce_qui_manque(atelier):
    """Le cas réel : le job est mort au milieu.

    On simule l'interruption en effaçant les nœuds des deux derniers plans
    du journal. Relancer doit produire DEUX images, pas quatre.
    """
    u, appels, tmp = atelier
    plans = _plans(u, 4)
    _fabriquer(u, plans, tmp / "img")
    assert len(appels) == 4

    with db.connexion() as conn:
        conn.execute("DELETE FROM etapes WHERE job_id = ? AND cle IN (?, ?)",
                     ("job_1", "image_002", "image_003"))

    appels.clear()
    planche = _fabriquer(u, plans, tmp / "img")
    assert sorted(appels) == ["plan_002.jpg", "plan_003.jpg"], (
        f"reprise partielle incorrecte : {sorted(appels)}"
    )
    assert len(planche.plans) == 4


# ── 2. L'ordre est celui du storyboard ─────────────────────────────────

def test_les_plans_sortent_dans_lordre_du_storyboard(atelier, monkeypatch):
    """Une planche triée par latence produirait un épisode mélangé.

    Le montage zippe `plans` et `images` position par position : si la
    planche revient dans l'ordre d'arrivée des réponses, chaque plan reçoit
    l'image d'un autre. Aucun test de COMPTAGE ne verrait la différence,
    c'est pourquoi celui-ci vérifie l'ordre.

    Les latences sont inversées exprès : le dernier plan répond en premier.
    """
    u, appels, tmp = atelier
    plans = _plans(u, 4)

    async def lent_a_lenvers(fn, prompt, destination, **k):
        numero = int(destination.stem.split("_")[1])
        await asyncio.sleep((4 - numero) * 0.01)
        return fn(prompt, destination, **k)

    vrai = images._produire
    monkeypatch.setattr(asyncio, "to_thread",
                        lambda fn, *a, **k: lent_a_lenvers(vrai, *a, **k))

    planche = _fabriquer(u, plans, tmp / "img")

    assert [p.numero for p in planche.plans] == [0, 1, 2, 3]
    assert [f.name for f in planche.fichiers] == [
        f"plan_{i:03d}.jpg" for i in range(4)]


# ── 3. Le plafond arrête la dépense ────────────────────────────────────

def test_le_plafond_budgetaire_arrete_la_production(atelier):
    """Paralléliser ne doit pas désarmer le plafond.

    Avec un parallélisme de 1, la borne est stricte : la production
    s'arrête dès que le plafond est atteint, et l'erreur est une
    ErreurBudget — pas une panne. `episode.py` et la CLI distinguent les
    deux, et les confondre ferait passer « tu as atteint ton plafond »
    pour « ta configuration est cassée ».
    """
    u, appels, tmp = atelier
    plans = _plans(u, 6)

    with pytest.raises(ErreurBudget):
        _fabriquer(u, plans, tmp / "img", budget_max=0.05, parallelisme=1)

    # 0,05 € de plafond à 0,02 € l'image : trois appels au plus (le
    # troisième part alors que 0,04 < 0,05, et c'est lui qui dépasse).
    assert len(appels) <= 3, (
        f"{len(appels)} images produites pour un plafond de 0,05 € : le "
        "plafond n'arrête plus la dépense"
    )


def test_un_plan_sans_image_ne_passe_jamais_pour_un_succes(atelier, monkeypatch):
    """Le montage exige une image par plan (`zip(..., strict=True)`).

    L'ordonnanceur laisse volontairement les branches indépendantes finir
    quand l'une échoue — c'est ce qu'on veut, le travail déjà payé est
    gardé. Mais l'appelant doit APPRENDRE l'échec, comme le faisait la
    version séquentielle en laissant remonter l'exception. Une planche
    incomplète rendue en silence casserait le montage bien plus loin, sur
    une erreur ffmpeg incompréhensible.
    """
    u, appels, tmp = atelier
    plans = _plans(u, 3)

    def casse_sur_le_second(prompt, destination, **k):
        if destination.name == "plan_001.jpg":
            raise ErreurBudget("panne simulée")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 2000)
        return 0.02, False

    monkeypatch.setattr(images, "_produire", casse_sur_le_second)

    with pytest.raises((ErreurBudget, Exception)) as e:
        _fabriquer(u, plans, tmp / "img")
    assert "plan(s) sans image" in str(e.value)
