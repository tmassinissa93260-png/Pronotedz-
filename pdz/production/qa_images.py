"""Vérifie visuellement, après coup et seulement pour les plans à risque,
que l'image générée montre vraiment ce que son plan devait montrer.

Ne tourne JAMAIS sur tous les plans — voir `plans_a_verifier()`. Ne demande
JAMAIS de score — voir `pdz/agents/analyse/qa_image.py` et la discussion
qui a précédé cet agent : un LLM qui note sa propre sortie avant que
l'image existe ne mesure rien de vérifiable, et une boucle de score coûte
un appel Groq de plus par plan pour rien.

Au maximum deux appels de vérification par plan concerné (jamais sur les
autres) : un premier verdict, et si FAIL, un correctif déterministe suivi
d'une seule regénération et d'un second verdict. Toujours FAIL ensuite ?
Le plan est marqué NEEDS_REVIEW et gardé tel quel — jamais de troisième
appel, jamais d'épisode bloqué pour un seul plan imparfait.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pdz.agents.analyse.qa_image import ImageQA
from pdz.moteur.erreurs import ErreurPdz
from pdz.moteur.pipeline import Contexte, executer_avec_relance
from pdz.production import fidelite_visuelle, images
from pdz.production.storyboard import PlanScript
from pdz.univers import Univers

log = logging.getLogger(__name__)


def plans_a_verifier(plans: list[PlanScript], numeros_realisme: set[int]) -> set[int]:
    """Quels plans méritent une vérification visuelle après génération.

    Deux signaux, tous les deux déjà calculés ailleurs dans le pipeline —
    zéro calcul supplémentaire, donc zéro coût de détection :
      · le plan a dû être « réparé » par `fidelite_visuelle.renforcer()` —
        son propre prompt oubliait déjà un élément obligatoire ;
      · le plan est passé par RealismWriter — une réécriture de prompt est
        un second endroit où un élément obligatoire peut disparaître.

    Un plan sans aucun des deux signaux n'a jamais montré de raison de
    douter de lui : le vérifier coûterait un appel Groq sans justification,
    exactement ce qu'on cherche à éviter.
    """
    return {p.numero for p in plans if p.corrections_fidelite} | numeros_realisme


def corriger_prompt(prompt: str, manquants: list[str], incorrects: list[str],
                    en_trop: list[str]) -> str:
    """Traduit un verdict FAIL en correction de texte, déterministe.

    Réutilise exactement le mécanisme de la première passe : ce que la QA
    visuelle a vu manquer devient un élément à rajouter, ce qu'elle a vu en
    trop ou à la place d'autre chose devient un élément à exclure. Aucune
    nouvelle logique, aucun appel IA de plus pour la correction elle-même.
    """
    prompt, _ = fidelite_visuelle.renforcer(prompt, manquants)
    return fidelite_visuelle.exclure(prompt, incorrects + en_trop)


async def verifier(plans: list[PlanScript], fichiers: list[Path], numeros: set[int],
                   univers: Univers, *, dossier: Path, profil: str,
                   budget_restant: float, job_id: str, chemin_univers: Path | None,
                   repliques_par_numero: dict[int, str],
                   ) -> tuple[list[dict], list[Path], float]:
    """Vérifie, et corrige au besoin, les seuls plans désignés par `numeros`.

    Renvoie (verifications, fichiers_a_jour, cout). `fichiers_a_jour` est
    `fichiers` avec, à la même position, les images qui ont dû être
    regénérées — l'animation et le montage n'ont jamais besoin de savoir
    qu'une vérification a eu lieu.
    """
    if not numeros:
        return [], fichiers, 0.0

    # Les fiches de personnages ont déjà été produites à l'étape Images :
    # les redemander ici coûte 0 € (cache sur disque), et garantit qu'une
    # éventuelle regénération reparte de la même image de référence — sans
    # ça, un personnage regénéré dériverait de son apparence sur ce plan.
    fiches = images.fiches(univers, dossier, profil=profil, cache=True,
                           job_id=job_id, chemin_univers=chemin_univers)

    fichiers = list(fichiers)
    verifications: list[dict] = []
    cout_total = 0.0

    for i, plan in enumerate(plans):
        if plan.numero not in numeros:
            continue

        ctx = Contexte(job_id=job_id, etape_cle="qa_images", profil=profil,
                       budget_restant=budget_restant - cout_total)
        try:
            verdict = await executer_avec_relance(ImageQA(), {
                "replique": repliques_par_numero.get(plan.numero, ""),
                "action": plan.action,
                "elements_obligatoires": plan.elements_obligatoires,
                "elements_a_exclure": plan.elements_a_exclure,
                "image": fichiers[i],
            }, ctx)
        except ErreurPdz as e:
            # Un fournisseur qui ne répond plus (quota épuisé, 5xx...) ne
            # doit jamais faire échouer l'ÉPISODE entier pour une simple
            # vérification optionnelle — voir la docstring du module.
            # Mesuré en production : la vidéo entière avortait alors que
            # le script, la voix et les 6 images étaient déjà payés.
            log.warning(
                "Plan %d : vérification visuelle impossible (%s) — gardé "
                "tel quel, non revérifié.", plan.numero, e.categorie,
            )
            cout_total += ctx.cout_engage
            continue
        cout_total += ctx.cout_engage

        if verdict["statut"] == "PASS":
            verifications.append({"numero": plan.numero, "statut": "PASS"})
            continue

        log.warning(
            "Plan %d : %s à la vérification visuelle — manquants=%s "
            "incorrects=%s en_trop=%s", plan.numero, verdict["statut"],
            verdict.get("manquants"), verdict.get("incorrects"), verdict.get("en_trop"),
        )

        # Un seul correctif, jamais de boucle — voir la docstring du module.
        prompt_corrige = corriger_prompt(
            plan.action, verdict.get("manquants", []),
            verdict.get("incorrects", []), verdict.get("en_trop", []),
        )
        perso = univers.personnage(plan.personnage)
        reference = fiches.get(perso.id) if perso else None
        try:
            cout, _ = images.regenerer(
                prompt_corrige, fichiers[i], univers=univers, reference=reference,
                profil=profil, budget_restant_pct=100.0, job_id=job_id,
            )
            cout_total += cout

            ctx2 = Contexte(job_id=job_id, etape_cle="qa_images", profil=profil,
                            budget_restant=budget_restant - cout_total)
            second = await executer_avec_relance(ImageQA(), {
                "replique": repliques_par_numero.get(plan.numero, ""),
                "action": prompt_corrige,
                "elements_obligatoires": plan.elements_obligatoires,
                "elements_a_exclure": plan.elements_a_exclure,
                "image": fichiers[i],
            }, ctx2)
            cout_total += ctx2.cout_engage
        except ErreurPdz as e:
            # Même principe que plus haut : un fournisseur en panne pendant
            # LA CORRECTION ne doit pas non plus faire échouer l'épisode.
            # On ne peut plus confirmer ce plan — NEEDS_REVIEW plutôt qu'un
            # PASS supposé, en gardant le dernier verdict réellement obtenu.
            log.warning(
                "Plan %d : correction/revérification impossible (%s) — "
                "marqué NEEDS_REVIEW, gardé tel quel.", plan.numero, e.categorie,
            )
            verifications.append({
                "numero": plan.numero, "statut": "NEEDS_REVIEW",
                "manquants": verdict.get("manquants", []),
                "incorrects": verdict.get("incorrects", []),
                "en_trop": verdict.get("en_trop", []),
            })
            continue

        if second["statut"] == "PASS":
            verifications.append({"numero": plan.numero, "statut": "PASS",
                                  "corrige": True})
        else:
            log.error(
                "Plan %d : encore %s après une regénération — marqué "
                "NEEDS_REVIEW, gardé tel quel plutôt que reconsommer du "
                "quota Groq.", plan.numero, second["statut"],
            )
            verifications.append({
                "numero": plan.numero, "statut": "NEEDS_REVIEW",
                "manquants": second.get("manquants", []),
                "incorrects": second.get("incorrects", []),
                "en_trop": second.get("en_trop", []),
            })

    return verifications, fichiers, cout_total
