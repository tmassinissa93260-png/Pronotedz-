"""Le SUJET brut peut mélanger le sujet réel et une remarque adressée à
l'assistant — BriefWriter l'isole dans `sujet_nettoye` (ecriture/brief@1.2.0),
et ScriptWriter ne doit plus jamais voir la version contaminée.

Bug réel : le champ SUJET se terminait par « la phrase que je vais lui
envoyer j'espère que ça pose pas de problème » — un aparté sur la
formulation, pas un événement — et cette phrase est devenue, mot pour mot,
la première réplique de l'épisode produit.
"""

from __future__ import annotations

import json

from tests.test_chaine_complete import SCRIPT_FACTICE, _produire, atelier  # noqa: F401

REMARQUE = "j'espère que ça pose pas de problème"
SUJET_BRUT = f"le trajet d'un message à travers le réseau. {REMARQUE}"
SUJET_NETTOYE = "le trajet d'un message à travers le réseau."


def test_le_script_recoit_le_sujet_nettoye_pas_le_brut(atelier, monkeypatch):
    vu = {}

    async def brief_qui_nettoie(self, entrees, ctx):
        ctx.facturer(0.001)
        sortie = {
            "sujet_nettoye": SUJET_NETTOYE,
            "strategie": {
                "mecanisme_hook": "x", "arc_narratif": "x",
                "ce_qui_retient": "x", "a_eviter": "x",
            },
            "beats": [
                {"position_pct": 0, "role": "hook", "quoi": "x"},
                {"position_pct": 33, "role": "tension", "quoi": "x"},
                {"position_pct": 66, "role": "curiosite", "quoi": "x"},
                {"position_pct": 90, "role": "payoff", "quoi": "x"},
            ],
        }
        return self.apres(sortie, entrees, ctx)

    async def script_qui_espionne(self, entrees, ctx):
        vu["situation"] = entrees["situation"]
        ctx.facturer(0.012)
        sortie = json.loads(json.dumps(SCRIPT_FACTICE))
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.brief.BriefWriter.executer", brief_qui_nettoie)
    monkeypatch.setattr("pdz.agents.ecriture.script.ScriptWriter.executer", script_qui_espionne)

    _, resultat = _produire(atelier, situation=SUJET_BRUT)

    assert vu["situation"] == SUJET_NETTOYE
    assert REMARQUE not in vu["situation"]
    assert resultat.video.exists()


def test_un_job_repris_davant_1_2_0_retombe_sur_le_sujet_brut(atelier, monkeypatch):
    """Non-régression : un brief mis en CACHE (base de données) avant
    l'ajout de `sujet_nettoye` n'a pas ce champ. Une reprise relit ce cache
    directement (jamais `BriefWriter.apres()`, voir `_fait()` dans
    episode.py) — elle ne doit pas planter, et doit continuer avec le SUJET
    brut comme avant."""
    from pdz import db

    _, premier = _produire(atelier, situation=SUJET_BRUT)

    with db.connexion() as conn:
        ligne = conn.execute(
            "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'brief'",
            (premier.job_id,),
        ).fetchone()
        brief_sans_sujet_nettoye = json.loads(ligne["resultat"])
        del brief_sans_sujet_nettoye["sujet_nettoye"]
        conn.execute(
            "UPDATE etapes SET resultat = ? WHERE job_id = ? AND cle = 'brief'",
            (json.dumps(brief_sans_sujet_nettoye), premier.job_id),
        )
        # Le script doit être refait pour qu'on voie ce que reçoit vraiment
        # ScriptWriter à la reprise.
        conn.execute("DELETE FROM etapes WHERE job_id = ? AND cle = 'script'",
                     (premier.job_id,))

    vu = {}

    async def script_qui_espionne(self, entrees, ctx):
        vu["situation"] = entrees["situation"]
        ctx.facturer(0.012)
        sortie = json.loads(json.dumps(SCRIPT_FACTICE))
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.script.ScriptWriter.executer",
                        script_qui_espionne)

    _, resultat = _produire(atelier, situation=SUJET_BRUT, job_id=premier.job_id)

    assert vu["situation"] == SUJET_BRUT
    assert resultat.video.exists()
