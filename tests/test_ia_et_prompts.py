"""Le registre de modèles, les prompts versionnés, et l'agent d'écriture.

L'appel réseau à Claude est remplacé par une réponse factice : on teste la
chaîne complète (prompt → appel → validation → sortie) sans clé d'API.
"""

import asyncio

import pytest
from pydantic import ValidationError as PydanticError

from pdz.agents.base import mots_par_replique, nb_plans_pour, nb_repliques_pour
from pdz.agents.ecriture.script import ScriptWriter
from pdz.ia.registre import registre
from pdz.moteur.erreurs import ErreurConfig, ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.prompts import charger
from pdz.univers import Univers

from pathlib import Path

FRUITS = Path("univers/fruit-island.yaml")


# ── Registre de modèles ──────────────────────────────────────────────────

def test_un_alias_se_resout_en_modele():
    res = registre().resoudre("qualite")
    assert res.modele.id
    assert "ecriture" in res.modele.fait


def test_le_profil_change_le_modele_dimages():
    eco = registre().resoudre("images", profil="economique")
    premium = registre().resoudre("images", profil="premium")
    assert eco.modele.id != premium.modele.id
    assert eco.modele.prix.par_image < premium.modele.prix.par_image


def test_un_budget_bas_bascule_sur_le_modele_moins_cher():
    normal = registre().resoudre("qualite", budget_restant_pct=100)
    serre = registre().resoudre("qualite", budget_restant_pct=10)
    assert serre.modele.id != normal.modele.id
    assert "budget" in serre.raison


def test_alias_inconnu_donne_un_message_utile():
    with pytest.raises(ErreurConfig) as e:
        registre().resoudre("licorne")
    assert "Connus" in str(e.value)


def test_le_cache_reduit_le_cout():
    m = registre().modeles["claude-sonnet-5"]
    sans = m.cout_texte(entree=4000, sortie=1500)
    avec = m.cout_texte(entree=4000, sortie=1500, cache_lu=2800)
    assert avec < sans


# ── Découpage : réplique ≠ plan ──────────────────────────────────────────

@pytest.mark.parametrize("duree", [30, 45, 90])
def test_il_y_a_environ_deux_plans_par_replique(duree):
    """Un plan toutes les ~1,75 s, une réplique toutes les ~3,5 s."""
    ratio = nb_plans_pour(duree) / nb_repliques_pour(duree)
    assert 1.7 <= ratio <= 2.3


def test_les_repliques_font_une_longueur_dicible():
    mots = mots_par_replique(45, nb_repliques_pour(45))
    assert all(7 <= m <= 12 for m in mots), mots


# ── Prompts versionnés ───────────────────────────────────────────────────

def test_le_prompt_se_charge_et_se_rend():
    p = charger("ecriture/script")
    assert p.ref == "ecriture/script@1.0.0"
    stable, _, message = p.rendre(
        contexte_univers="UNIVERS : test",
        situation="une dispute",
        duree_s=45, nb_repliques=13,
        mots_par_replique=[9] * 13, nb_plans_vises=26,
        resume_precedent="",
    )
    assert "UNIVERS : test" in stable
    assert "une dispute" in message


def test_une_variable_oubliee_echoue_tout_de_suite():
    with pytest.raises(ErreurValidation) as e:
        charger("ecriture/script").rendre(situation="x")
    assert "manquantes" in str(e.value)


# ── L'agent, avec un Claude factice ──────────────────────────────────────

def _reponse_factice(univers, nb=13, avec_relance=True, personnage=None):
    perso = personnage or univers.personnages[0].id
    return {
        "titre": "La trahison",
        "promesse": "Elle va tout avouer",
        "derniere_image": "retour sur le premier plan",
        "repliques": [
            {
                "numero": i + 1,
                "personnage": perso,
                "replique": "Tu savais depuis le début et tu n as rien dit",
                "action": "elle se retourne lentement",
                "emotion": "colere",
                "reaction_de": "",
                "relance": avec_relance and i == 5,
            }
            for i in range(nb)
        ],
    }


def _contexte():
    return Contexte(job_id="j", etape_cle="script", profil="equilibre",
                    budget_restant=0.60)


def test_lagent_valide_et_enrichit_la_sortie():
    u = Univers.charger(FRUITS)
    agent = ScriptWriter()
    sortie = agent.apres(_reponse_factice(u), {"univers": u}, _contexte())
    assert sortie["nb_repliques"] == 13
    assert sortie["mots_total"] > 0
    assert sortie["duree_parlee_estimee_s"] > 0


def test_lagent_refuse_un_personnage_inconnu():
    u = Univers.charger(FRUITS)
    mauvais = _reponse_factice(u, personnage="pasteque_inexistante")
    with pytest.raises(ErreurValidation) as e:
        ScriptWriter().apres(mauvais, {"univers": u}, _contexte())
    assert "inconnu de l'univers" in str(e.value)


def test_lagent_refuse_un_script_sans_relance():
    u = Univers.charger(FRUITS)
    plat = _reponse_factice(u, avec_relance=False)
    with pytest.raises(ErreurValidation) as e:
        ScriptWriter().apres(plat, {"univers": u}, _contexte())
    assert "relance" in str(e.value)


def test_la_signature_change_avec_la_version_du_prompt():
    """C'est ce qui invalide le cache automatiquement quand un prompt bouge."""
    sig = ScriptWriter().signature()
    assert sig["prompt"] == "ecriture/script@1.0.0"
    assert sig["agent"] == "script"


def test_les_variables_du_prompt_sont_calculees_depuis_lunivers():
    u = Univers.charger(FRUITS)
    v = ScriptWriter().variables({"univers": u, "situation": "test"}, _contexte())
    assert v["duree_s"] == u.duree_cible_s
    assert len(v["mots_par_replique"]) == v["nb_repliques"]
    assert "Strawberina" in v["contexte_univers"]
