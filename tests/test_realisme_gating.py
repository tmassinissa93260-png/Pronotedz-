"""RealismWriter ne tourne que sur les plans que le filtre déterministe
flague — jamais sur tous, à chaque fois.

Le filtre (`pdz.production.risque_prompt`, testé isolément dans
tests/test_risque_prompt.py) est réutilisé ici en conditions réelles, à
travers `episode.produire()` : c'est la seule façon de vérifier que le
branchement dans `episode.py` respecte vraiment le filtre, pas seulement
que le filtre lui-même fonctionne.
"""

from __future__ import annotations

import json

from tests.test_chaine_complete import SCRIPT_FACTICE, _produire, atelier  # noqa: F401


def _script_avec_action(action_risquee: str):
    async def faux_script(self, entrees, ctx):
        ctx.facturer(0.012)
        sortie = json.loads(json.dumps(SCRIPT_FACTICE))
        sortie["repliques"][0]["action"] = action_risquee
        return self.apres(sortie, entrees, ctx)
    return faux_script


def test_realisme_est_saute_quand_rien_nest_a_risque(atelier, monkeypatch):
    """Comportement par défaut de l'atelier : SCRIPT_FACTICE ne décrit rien
    de risqué (texte lisible, logo, visage) — RealismWriter ne doit jamais
    être appelé, 0 coût, 0 appel Groq en plus."""
    appels = {"n": 0}

    async def compte(self, entrees, ctx):
        appels["n"] += 1
        ctx.facturer(0.001)
        sortie = {"plans": [{"numero": p.numero, "prompt_image": p.action}
                            for p in entrees["plans"]]}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.realisme.RealismWriter.executer", compte)

    _, resultat = _produire(atelier)

    assert appels["n"] == 0
    assert "realisme" not in resultat.etapes_reprises


def test_realisme_est_appele_quand_un_plan_decrit_un_risque(atelier, monkeypatch):
    """Une action qui implique un écran affichant du texte lisible doit
    déclencher RealismWriter — c'est exactement le cas mesuré cette nuit."""
    appels = {"n": 0}

    async def compte(self, entrees, ctx):
        appels["n"] += 1
        ctx.facturer(0.001)
        sortie = {"plans": [{"numero": p.numero, "prompt_image": p.action}
                            for p in entrees["plans"]]}
        return self.apres(sortie, entrees, ctx)

    async def prompts_qui_gardent_laction(self, entrees, ctx):
        # Le mock par défaut de l'atelier écrit "prompt riche N" et perd le
        # contenu de `action` — ici, on le garde pour vérifier que le risque
        # écrit par ScriptWriter atteint bien le filtre en aval.
        ctx.facturer(0.001)
        sortie = {"plans": [{"numero": p.numero, "prompt_image": p.action}
                            for p in entrees["plans"]]}
        return self.apres(sortie, entrees, ctx)

    async def qa_toujours_pass(self, entrees, ctx):
        # Un plan passé par RealismWriter déclenche aussi la QA image (voir
        # tests/test_qa_images_gating.py) — sans ce mock, ce test essaierait
        # un vrai appel réseau.
        ctx.facturer(0.0005)
        return self.apres(
            {"statut": "PASS", "manquants": [], "incorrects": [], "en_trop": []},
            entrees, ctx,
        )

    monkeypatch.setattr("pdz.agents.ecriture.realisme.RealismWriter.executer", compte)
    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        prompts_qui_gardent_laction)
    monkeypatch.setattr("pdz.agents.ecriture.script.ScriptWriter.executer",
                        _script_avec_action("phone screen showing a conversation visible"))
    monkeypatch.setattr("pdz.agents.analyse.qa_image.ImageQA.executer", qa_toujours_pass)

    _, resultat = _produire(atelier)

    assert appels["n"] == 1
    assert resultat.video.exists()
