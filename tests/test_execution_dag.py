"""L'ordonnanceur : parallélisme, reprise par nœud, et échecs qui n'emportent
pas tout.

Ce que ces tests protègent :

  · **la parallélisation réelle** — profondeur et masque partent ensemble ;
  · **la reprise par NŒUD** — relancer ne refait pas ce qui est fait, et ne
    le repaie pas ;
  · **un échec n'arrête pas le DAG** — les branches indépendantes
    continuent, sinon on perdrait le travail déjà payé de la même vague ;
  · **une seule autorité** — l'ordonnanceur appelle le journal, il n'invente
    ni cache ni reprise.
"""

from __future__ import annotations

import asyncio

import pytest

from pdz import db
from pdz.contracts import ExecutionPlan, NoeudExecution, StatutNoeud
from pdz.execution import executer
from pdz.moteur.erreurs import ErreurFournisseur, ErreurValidation


@pytest.fixture
def base(tmp_path, monkeypatch):
    from pdz.config import Config, config

    config.cache_clear()
    monkeypatch.setattr("pdz.config.config", lambda: Config(donnees=tmp_path))
    monkeypatch.setattr("pdz.db.config", lambda: Config(donnees=tmp_path))
    db.init()
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO jobs (id, type, statut, entree, profil, budget_max,"
            " cout_total, cree_le, maj_le) VALUES (?,?,?,?,?,?,?,?,?)",
            ("job_1", "video", "en_cours", "{}", "equilibre", 5.0, 0.0,
             db.maintenant(), db.maintenant()),
        )
        # Un second job pour vérifier que le CACHE traverse les jobs, là où
        # la reprise ne le fait pas.
        conn.execute(
            "INSERT INTO jobs (id, type, statut, entree, profil, budget_max,"
            " cout_total, cree_le, maj_le) VALUES (?,?,?,?,?,?,?,?,?)",
            ("job_2", "video", "en_cours", "{}", "equilibre", 5.0, 0.0,
             db.maintenant(), db.maintenant()),
        )
    yield tmp_path
    config.cache_clear()


def _plan_2_5d() -> ExecutionPlan:
    """Le DAG réel d'un plan en 2.5D : image, puis profondeur ET masque en
    parallèle, puis compositing."""
    return ExecutionPlan(shot_id="shot_001", noeuds=(
        NoeudExecution(noeud_id="image", operation="image", cout_estime_eur=0.003),
        NoeudExecution(noeud_id="profondeur", operation="depth", depend_de=("image",)),
        NoeudExecution(noeud_id="masque", operation="mask", depend_de=("image",)),
        NoeudExecution(noeud_id="composite", operation="comp",
                       depend_de=("profondeur", "masque")),
    ))


def _operations(trace: list, *, echoue: str = "", cout: float = 0.0,
                dossier=None):
    """Des opérations qui produisent de VRAIS fichiers.

    Indispensable : le journal revérifie que les fichiers cités par une
    étape terminée existent encore (acquis de la PHASE 5). Des chemins
    inventés feraient refuser toute reprise — le mécanisme ferait
    exactement son travail, et le test mesurerait autre chose que ce qu'il
    croit mesurer.
    """
    async def _faire(noeud, entrees):
        trace.append(("debut", noeud.noeud_id))
        await asyncio.sleep(0.01)
        if noeud.operation == echoue:
            raise ErreurFournisseur(f"échec simulé sur {noeud.noeud_id}")
        trace.append(("fin", noeud.noeud_id))
        sortie = {"cout_eur": cout}
        if dossier is not None:
            fichier = dossier / f"{noeud.noeud_id}.png"
            fichier.write_bytes(b"x")
            sortie["fichier"] = str(fichier)
        return sortie

    return {op: _faire for op in ("image", "depth", "mask", "comp")}


# ── Parallélisme ─────────────────────────────────────────────────────────

def test_les_noeuds_independants_partent_ensemble(base):
    """Profondeur et masque ne dépendent que de l'image : les exécuter l'un
    après l'autre doublerait l'attente pour rien."""
    trace = []
    asyncio.run(executer(_plan_2_5d(), _operations(trace), job_id="job_1"))

    debuts = [n for evt, n in trace if evt == "debut"]
    # Les deux démarrent avant que l'un des deux ne finisse.
    i_profondeur, i_masque = debuts.index("profondeur"), debuts.index("masque")
    fins = [n for evt, n in trace if evt == "fin"]
    assert abs(i_profondeur - i_masque) == 1
    assert fins.index("composite") == len(fins) - 1


def test_l_ordre_des_dependances_est_respecte(base):
    trace = []
    asyncio.run(executer(_plan_2_5d(), _operations(trace), job_id="job_1"))
    fins = [n for evt, n in trace if evt == "fin"]
    assert fins.index("image") < fins.index("profondeur")
    assert fins.index("profondeur") < fins.index("composite")


def test_un_plan_simple_reste_un_seul_noeud(base):
    """Forcer tous les plans à ressembler à un graphe complexe n'apporterait
    rien."""
    plan = ExecutionPlan(noeuds=(NoeudExecution(noeud_id="video", operation="image"),))
    resultat = asyncio.run(executer(plan, _operations([]), job_id="job_1"))
    assert resultat.complet
    assert len(resultat.sorties) == 1


def test_le_parallelisme_est_plafonne(base):
    """Dix appels simultanés chez le même fournisseur se font limiter, et
    dix ffmpeg d'un coup ne vont pas plus vite."""
    simultanes, maximum = [], []

    async def _faire(noeud, entrees):
        simultanes.append(noeud.noeud_id)
        maximum.append(len(simultanes))
        await asyncio.sleep(0.02)
        simultanes.remove(noeud.noeud_id)
        return {"fichier": "x"}

    plan = ExecutionPlan(noeuds=tuple(
        NoeudExecution(noeud_id=f"n{i}", operation="image") for i in range(8)))
    asyncio.run(executer(plan, {"image": _faire}, job_id="job_1",
                         parallelisme_max=2))
    assert max(maximum) <= 2


# ── Reprise ──────────────────────────────────────────────────────────────

def test_relancer_ne_refait_pas_ce_qui_est_fait(base):
    """La reprise est par NŒUD : un composite raté ne doit pas refaire la
    carte de profondeur."""
    premier = []
    asyncio.run(executer(_plan_2_5d(), _operations(premier, dossier=base),
                         job_id="job_1"))

    second = []
    resultat = asyncio.run(executer(_plan_2_5d(), _operations(second, dossier=base),
                                    job_id="job_1"))
    assert second == [], "aucun nœud ne devait être réexécuté"
    assert len(resultat.reutilises) == 4


def test_la_reprise_ne_repaie_rien(base):
    """Et elle sait dire ce qu'elle a évité — sans quoi on ne saurait pas si
    le cache sert à quelque chose."""
    plan = _plan_2_5d()
    asyncio.run(executer(plan, _operations([], cout=0.05, dossier=base),
                         job_id="job_1"))
    seconde = asyncio.run(executer(plan, _operations([], cout=0.05, dossier=base),
                                   job_id="job_1"))
    assert seconde.cout_eur == 0.0
    assert seconde.cout_evite_eur > 0


def test_un_noeud_dont_le_fichier_a_disparu_est_refait(base):
    """L'acquis monté au noyau en PHASE 5, appliqué au DAG."""
    fichier = base / "image.png"

    async def _produit(noeud, entrees):
        fichier.write_bytes(b"x")
        return {"fichier": str(fichier)}

    plan = ExecutionPlan(noeuds=(NoeudExecution(noeud_id="image", operation="image"),))
    asyncio.run(executer(plan, {"image": _produit}, job_id="job_1"))

    fichier.unlink()
    trace = []

    async def _retrace(noeud, entrees):
        trace.append(noeud.noeud_id)
        return await _produit(noeud, entrees)

    asyncio.run(executer(plan, {"image": _retrace}, job_id="job_1"))
    assert trace == ["image"], "le nœud devait être refait"


def test_le_cache_sert_un_noeud_calcule_par_un_autre_job(base):
    """Distinct de la reprise : celle-ci est par job, le cache par empreinte."""
    plan = ExecutionPlan(noeuds=(
        NoeudExecution(noeud_id="image", operation="image", cle_cache="emp_abc"),))
    asyncio.run(executer(plan, _operations([], dossier=base), job_id="job_1"))

    trace = []
    resultat = asyncio.run(executer(plan, _operations(trace, dossier=base),
                                    job_id="job_2"))
    assert trace == [], "le cache devait servir"
    assert resultat.reutilises == ["image"]


# ── Échecs ───────────────────────────────────────────────────────────────

def test_un_echec_n_arrete_pas_les_branches_independantes(base):
    """Tout arrêter perdrait le travail déjà payé de la même vague."""
    trace = []
    resultat = asyncio.run(executer(_plan_2_5d(), _operations(trace, echoue="depth"),
                                    job_id="job_1"))
    assert "profondeur" in resultat.echoues
    assert "masque" in resultat.sorties, "la branche indépendante devait aboutir"


def test_un_noeud_dont_la_dependance_a_echoue_est_ignore(base):
    """On le saute plutôt que de le lancer pour le voir échouer sur des
    entrées manquantes."""
    resultat = asyncio.run(executer(_plan_2_5d(), _operations([], echoue="depth"),
                                    job_id="job_1"))
    assert "composite" in resultat.echoues
    statuts = {n.noeud_id: n.statut for n in resultat.plan.noeuds}
    assert statuts["composite"] is StatutNoeud.IGNORE
    assert statuts["profondeur"] is StatutNoeud.ECHOUE


def test_un_plan_avec_echec_n_est_pas_complet(base):
    resultat = asyncio.run(executer(_plan_2_5d(), _operations([], echoue="depth"),
                                    job_id="job_1"))
    assert not resultat.complet


def test_une_operation_inconnue_echoue_avec_un_message_utile(base):
    plan = ExecutionPlan(noeuds=(
        NoeudExecution(noeud_id="x", operation="teleportation"),))
    resultat = asyncio.run(executer(plan, {}, job_id="job_1"))
    erreur = resultat.plan.noeuds[0].erreur
    assert "opération inconnue" in erreur and "teleportation" in erreur


def test_la_politique_de_relance_est_celle_du_noeud(base):
    """Une carte de profondeur locale et un appel vidéo en file d'attente
    n'appellent pas la même politique."""
    essais = []

    async def _capricieux(noeud, entrees):
        essais.append(1)
        if len(essais) < 3:
            raise ErreurValidation("pas encore")
        return {"fichier": "ok"}

    plan = ExecutionPlan(noeuds=(
        NoeudExecution(noeud_id="x", operation="image", tentatives_max=3),))
    resultat = asyncio.run(executer(plan, {"image": _capricieux}, job_id="job_1"))
    assert resultat.complet
    assert len(essais) == 3
    assert resultat.plan.noeuds[0].tentative == 3


def test_sans_relance_un_echec_est_definitif(base):
    essais = []

    async def _toujours_rate(noeud, entrees):
        essais.append(1)
        raise ErreurValidation("non")

    plan = ExecutionPlan(noeuds=(
        NoeudExecution(noeud_id="x", operation="image", tentatives_max=1),))
    asyncio.run(executer(plan, {"image": _toujours_rate}, job_id="job_1"))
    assert len(essais) == 1


# ── Coût ─────────────────────────────────────────────────────────────────

def test_le_cout_reel_est_agrege_et_remonte_sur_le_job(base):
    asyncio.run(executer(_plan_2_5d(), _operations([], cout=0.05), job_id="job_1"))
    with db.connexion() as conn:
        total = conn.execute("SELECT cout_total FROM jobs WHERE id = ?",
                             ("job_1",)).fetchone()
    assert total["cout_total"] == pytest.approx(0.20)


def test_les_sorties_alimentent_les_noeuds_suivants(base):
    recues = {}

    async def _faire(noeud, entrees):
        recues[noeud.noeud_id] = dict(entrees)
        return {"fichier": f"/x/{noeud.noeud_id}"}

    asyncio.run(executer(_plan_2_5d(),
                         {op: _faire for op in ("image", "depth", "mask", "comp")},
                         job_id="job_1"))
    assert recues["profondeur"]["image"]["fichier"] == "/x/image"
    assert set(recues["composite"]) == {"profondeur", "masque"}
