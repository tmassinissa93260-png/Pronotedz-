"""Décide **quels** plans méritent d'être animés, et les anime.

Le poste le plus cher du système, et de loin. À 0,046 €/seconde chez Kling,
animer les 26 plans d'un épisode de 45 secondes coûte 2 € — trois fois le
plafond par vidéo. Animer au hasard six plans sur vingt-six coûte pareil qu'en
animer six bien choisis, pour un résultat très différent.

D'où ce module, qui ne fait que deux choses :

  1. **classer les plans** par ce que l'animation leur apporterait ;
  2. **s'arrêter au budget**, pas au chiffre annoncé par le profil.

Le second point est celui qui manque partout ailleurs. Un profil qui promet
« 6 plans animés » sans regarder ce qu'il reste en caisse produit une erreur
de facturation au onzième épisode. Ici, le nombre réel est calculé, et la
raison du plafond est écrite dans le journal.

Les plans non animés ne restent pas fixes pour autant : le montage leur
applique un mouvement de caméra (recadrage glissant, gratuit), et le mode
« vie » y ajoute parallaxe et particules — également gratuit. Un plan animé
par un modèle vidéo reste très supérieur ; c'est pour ça qu'on choisit où les
mettre au lieu d'en saupoudrer partout.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pdz import repair
from pdz.backends import backend_video
from pdz.contracts import (
    Certitude,
    ExperienceRecord,
    ModeEchec,
    RenderSpecExecutable,
    Strategie,
    TypeReparation,
)
from pdz.ia.registre import registre
from pdz.memory import ExperienceMemory
from pdz.moteur.erreurs import ErreurPdz
from pdz.production import motion_program, verification_mouvement
from pdz.univers import Univers

log = logging.getLogger(__name__)

# Ces deux constantes ne sont plus que des REPLIS, pour un `modeles.yaml`
# qui ne déclarerait aucun `durees_s`. La durée qu'un modèle livre vraiment
# est une propriété DU MODÈLE et vit désormais à côté de lui (voir
# `registre.Modele.durees_s`) : les ~4,84 s ci-dessous ont été mesurées sur
# ltx-video, et les appliquer à Kling — qui livre 10 s — écartait des plans
# que le modèle en place traitait très bien (5 sur 6, épisode #74).

# Durée demandée par défaut. Les modèles image→vidéo facturent à la seconde.
DUREE_CLIP_S = 5

# Plafond par défaut. MESURÉ sur ltx-video (runs #57, #65, #66) : ce endpoint
# rend ~4,84 s qu'on lui demande 5 ou 10 — `duration` n'y a aucun effet
# au-delà. C'est ce plafond-là qui décide si un plan mérite l'appel payant.
DUREE_REELLE_MAX_S = 5.0

# Marge sous laquelle un clip rendu plus court que la durée allouée est
# encore acceptable (arrondis d'encodage). Au-delà, le montage tronquerait
# la vidéo pour ce plan — voir la mesure en production dans `animer()`.
TOLERANCE_DUREE_S = 0.3

# Les émotions qui gagnent le plus à bouger. Une colère figée est une image
# ratée ; un personnage calme figé passe très bien.
EMOTIONS_FORTES = {"colere": 2.0, "surprise": 2.0, "peur": 1.6,
                   "joie": 1.2, "tristesse": 0.8, "mepris": 0.8,
                   "gene": 0.5, "calme": 0.0}


@dataclass
class Candidature:
    """Un plan, sa note, et ce qui la justifie."""

    index: int
    note: float
    raison: str


@dataclass
class PlanAnime:
    index: int
    fichier: Path
    anime: bool
    methode: str            # « modele » | « vie » | « camera »
    cout: float = 0.0
    # Trace fine de CE QUI S'EST PASSÉ pour ce plan — « methode » seul
    # mélangeait déjà un vrai clip modèle et un repli local sous le même
    # `anime=True` (voir l'enquête run #66, § résumé trompeur). Avec ce
    # champ, `methode == "modele"` implique TOUJOURS `diagnostic ==
    # "mouvement_confirme"` — plus jamais un simple succès d'API. Valeurs :
    # "mouvement_confirme" (methode="modele"), "rejete_duree",
    # "rejete_mouvement", "timeout", "erreur_appel", "hors_portee"
    # (méthode="vie"/"camera" — pourquoi le modèle n'a pas été retenu),
    # "non_elu" (jamais tenté, budget/note).
    diagnostic: str = ""
    # Le `FailureDiagnosis` complet quand il y en a un — la CAUSE, avec sa
    # confiance et ses preuves, là où `diagnostic` ci-dessus ne porte qu'une
    # étiquette. Deux étiquettes distinctes ne pouvaient pas exprimer qu'un
    # même symptôme (« ça ne bouge pas assez ») a des causes opposées :
    # un rendu statique et une caméra qui mange le plan appellent des
    # corrections inverses.
    #
    # `None` sur les plans jamais tentés : il n'y a rien à diagnostiquer
    # d'une génération qui n'a pas eu lieu.
    cause: object | None = None


def duree_max_du_modele(profil: str = "equilibre") -> float:
    """Le plafond de durée du modèle d'animation réellement résolu.

    Longtemps une constante de module, ce qui était faux dès qu'un second
    modèle est entré dans `modeles.yaml` : les ~4,84 s sont une propriété
    MESURÉE de ltx-video, pas une loi de l'image→vidéo. Kling en livre 10.
    Appliquer le plafond de l'un à l'autre faisait sauter des plans que le
    modèle en place savait très bien traiter (5 sur 6, épisode #74).
    """
    try:
        res = registre().resoudre("animation", profil=profil,
                                  repli_si_cle_absente=True)
    except ErreurPdz:
        return DUREE_REELLE_MAX_S
    return res.modele.duree_max_s or DUREE_REELLE_MAX_S


def _duree_a_demander(duree_requise: float, profil: str, defaut: int) -> int:
    """Ce qu'on ENVOIE au fournisseur pour ce plan précis."""
    try:
        res = registre().resoudre("animation", profil=profil,
                                  repli_si_cle_absente=True)
    except ErreurPdz:
        return defaut
    if not res.modele.durees_s:
        return defaut
    return res.modele.duree_facturable(duree_requise, TOLERANCE_DUREE_S)


def noter(plans: list[dict], *, duree_max_s: float = DUREE_REELLE_MAX_S) -> list[Candidature]:
    """Classe les plans par ce que l'animation leur apporterait.

    Les critères, du plus fort au plus faible :
      · **le premier plan** — trois secondes décident de tout, et c'est le
        seul endroit où un mouvement réel se remarque à coup sûr ;
      · **une relance** — le temps fort de rétention que ScriptWriter place
        exprès toutes les 15-20 s (`repliques[].relance`, voir
        `pdz/agents/ecriture/script.py`) mérite de bouger autant que
        l'accroche : c'est l'endroit où le spectateur décide de rester ;
      · **l'émotion** — un visage qui bouge vaut surtout pour les émotions
        fortes ;
      · **la durée** — un plan de 3 s figé se voit, un plan de 1 s non, MAIS
        seulement si cette durée reste dans ce que le modèle rend
        réellement (`DUREE_REELLE_MAX_S`) — un plan plus long que ça est
        voué à échouer le contrôle de durée post-génération quoi qu'on lui
        demande (mesuré, enquête run #66) : le noter comme un atout aurait
        fait gagner exactement les plans les moins susceptibles de
        réussir, ce qui est arrivé en production (le plan le mieux noté de
        l'épisode #66 n'a reçu aucune vraie animation) ;
      · **une intensité de mouvement forte**, quand ShotPromptWriter l'a
        décidée pour ce plan précis (`intensite_mouvement`, voir
        `pdz/agents/ecriture/plans.py`) — relie enfin la sélection à une
        vraie décision de mouvement plutôt qu'à une intuition ;
      · **les plans de réaction** sont pénalisés : l'immobilité y est un
        choix de montage valable, pas un défaut ;
      · **un défaut visuel déjà constaté** (`besoin_revue`, voir
        `pdz/production/qa_images.py`) est fortement pénalisé — animer une
        image qu'on sait déjà fautive gaspille le poste le plus cher du
        pipeline sans rien améliorer.
    """
    candidatures: list[Candidature] = []

    for i, plan in enumerate(plans):
        note, raisons = 0.0, []

        if i == 0:
            note += 3.0
            raisons.append("accroche")

        if plan.get("relance"):
            note += 1.5
            raisons.append("relance (temps fort de rétention)")

        emotion = plan.get("emotion", "calme")
        if (bonus := EMOTIONS_FORTES.get(emotion, 0.0)):
            note += bonus
            raisons.append(emotion)

        duree = float(plan.get("duree_s", 0) or 0)
        if 3.0 <= duree <= duree_max_s:
            note += 1.0
            raisons.append(f"{duree:.1f} s à l'écran, dans la capacité du modèle")
        elif duree > duree_max_s:
            note -= 0.5
            raisons.append(
                f"{duree:.1f} s hors de portée du modèle (max ~{duree_max_s:.1f} s)")
        elif duree < 1.2:
            note -= 1.0
            raisons.append("trop court pour se voir")

        if plan.get("intensite_mouvement") == "fort":
            note += 0.8
            raisons.append("mouvement fort décidé pour ce plan")

        if plan.get("reaction"):
            note -= 0.8
            raisons.append("plan de réaction")

        if i == len(plans) - 1:
            note += 0.8
            raisons.append("dernier plan")

        if plan.get("besoin_revue"):
            note -= 2.5
            raisons.append("défaut visuel déjà constaté (QA)")

        candidatures.append(Candidature(i, round(note, 2), ", ".join(raisons)))

    candidatures.sort(key=lambda c: (-c.note, c.index))
    return candidatures


def combien_animer(nb_plans: int, budget_restant: float, *,
                   profil: str = "equilibre",
                   duree_clip_s: int = DUREE_CLIP_S) -> tuple[int, str]:
    """Combien de plans on peut réellement animer. Renvoie (nombre, raison).

    Trois plafonds s'appliquent, et c'est le plus bas qui gagne : le profil,
    le budget qui reste, et le nombre de plans existants. La raison est
    renvoyée pour être journalisée — « 2 plans animés » sans explication
    ressemble à une panne.
    """
    reg = registre()
    if reg.option_profil(profil, "animer", True) is False:
        return 0, f"profil « {profil} » : animation désactivée"

    demande = int(reg.option_profil(profil, "plans_animes_max", 6))

    res = reg.resoudre("animation", profil=profil, repli_si_cle_absente=True)
    # Le palier le PLUS CHER que ce modèle peut facturer, pas le plus court :
    # depuis que la durée demandée s'adapte au plan, estimer sur 5 s alors
    # qu'un plan peut en coûter 10 promettrait un nombre de plans que le
    # budget ne couvre pas. Mieux vaut sous-estimer ce qu'on peut s'offrir.
    cout_unitaire = res.modele.cout_unites(
        res.modele.duree_max_s or duree_clip_s, "seconde")
    if cout_unitaire <= 0:
        payables = demande
    else:
        payables = int(max(0.0, budget_restant) // cout_unitaire)

    combien = min(demande, payables, nb_plans)

    if combien == payables < demande:
        raison = (f"budget : {budget_restant:.2f} € restants à "
                  f"{cout_unitaire:.3f} €/plan")
    elif combien == nb_plans < demande:
        raison = f"seulement {nb_plans} plans"
    else:
        raison = f"profil « {profil} »"

    return combien, raison


def animer(plans: list[dict], images: list[Path], univers: Univers,
           dossier: Path, *, budget_restant: float,
           profil: str = "equilibre", duree_clip_s: int = DUREE_CLIP_S,
           job_id: str | None = None,
           vie_pour_le_reste: bool = True) -> list[PlanAnime]:
    """Anime les plans qui le méritent, dans la limite du budget.

    Renvoie une entrée par plan, animé ou non : le montage a besoin de savoir
    lesquels sont des clips (durée imposée par le fichier) et lesquels sont
    des images fixes (durée imposée par le montage).
    """
    if len(images) != len(plans):
        raise ErreurPdz(
            f"{len(plans)} plans mais {len(images)} images : le storyboard et "
            "la planche ne sont pas d'accord."
        )

    dossier.mkdir(parents=True, exist_ok=True)
    duree_max_s = duree_max_du_modele(profil)
    combien, raison = combien_animer(len(plans), budget_restant, profil=profil,
                                     duree_clip_s=duree_clip_s)
    classement = noter(plans, duree_max_s=duree_max_s)
    elus, ecartes = _filtrer_par_strategie(
        [c.index for c in classement[:combien]], plans, images,
        budget_restant=budget_restant, profil=profil)

    log.info("Animation : %d plan(s) sur %d — %s", combien, len(plans), raison)
    for c in classement[:combien]:
        if c.index in elus:
            log.info("  · plan %d (note %.1f) : %s", c.index, c.note, c.raison)
    for index, pourquoi in ecartes.items():
        log.info("  · plan %d élu mais NON payé — %s", index, pourquoi)

    resultats: list[PlanAnime] = []
    depense = 0.0

    for i, (plan, image) in enumerate(zip(plans, images, strict=True)):
        if i in elus:
            destination = dossier / f"anime_{i:03d}.mp4"
            duree_requise = float(plan.get("duree_s") or 0)
            if duree_requise > duree_max_s:
                # Mesuré (enquête run #65 ET #66, deux valeurs de `duration`
                # différentes, même résultat) : le modèle ne rend jamais plus
                # que ~4,84 s, quel que soit ce qu'on demande. Un plan qui a
                # besoin de PLUS que `DUREE_REELLE_MAX_S` est donc voué à
                # échouer la vérification plus bas quoi qu'on envoie comme
                # `duration` : autant épargner l'appel payant (~0,09 €) et
                # les 1 à 3 minutes d'attente, et aller direct au repli
                # local, qui n'a lui aucune limite de durée.
                log.info(
                    "Plan %d : %.2f s requis, au-delà des ~%.1f s que le "
                    "modèle rend réellement — animation modèle sautée, "
                    "repli direct.", i, duree_requise, duree_max_s,
                )
                resultats.append(_repli(i, image, dossier, plan, vie_pour_le_reste,
                                        duree_clip_s, diagnostic="hors_portee"))
                continue
            reste = max(0.0, budget_restant - depense)
            # Le plus petit palier qui couvre le plan, pas une constante :
            # facturé à la seconde, demander 10 s pour un plan de 4 s serait
            # payer le double pour rien. Un modèle à palier unique (ltx-video)
            # retombe sur sa seule valeur, donc rien ne change pour lui.
            duree_demandee = _duree_a_demander(duree_requise, profil, duree_clip_s)
            # Le métier décrit CE QU'IL VEUT ; le backend décide comment
            # l'obtenir et chez qui. Aucun nom de fournisseur n'apparaît plus
            # ici — c'est la réparation de l'écart relevé en PHASE 1.
            spec = RenderSpecExecutable(
                shot_id=str(i),
                strategie=Strategie.DIRECT_I2V,
                duree_s=duree_demandee,
                prompt=_prompt_mouvement(plan, univers),
                image_depart=str(image),
                parametres={
                    "destination": str(destination),
                    "profil": profil,
                    "budget_restant_pct": str(100.0 if reste > 0 else 0.0),
                    "job_id": job_id or "",
                    "agent": "animation",
                },
            )
            try:
                cout = backend_video(profil).executer(spec).cout_eur
            except ErreurPdz as e:
                # Une animation ratée n'annule pas l'épisode : le plan reste
                # une image fixe, que le montage saura faire bouger.
                log.warning("Plan %d non animé (%s) : %s", i, e.categorie, e)
                diag = "timeout" if e.categorie == "ErreurReseau" else "erreur_appel"
                resultats.append(_repli(i, image, dossier, plan, vie_pour_le_reste,
                                        duree_clip_s, diagnostic=diag))
                continue

            depense += cout
            # Le mouvement est jugé sur la fenêtre que le montage gardera
            # VRAIMENT (`trim=duration=plan.duree_s`), pas sur le clip
            # entier — sinon un sursaut de mouvement dans la portion coupée
            # ferait accepter un plan que le spectateur verra immobile. La
            # durée, elle, reste mesurée sur le clip complet.
            verdict = verification_mouvement.verifier(
                destination, fenetre_s=duree_requise)
            duree_ok = verdict.fichier_valide and verdict.duree_s >= duree_requise - TOLERANCE_DUREE_S

            # Le verdict, traduit en rapport d'observation puis confronté à
            # ce que le plan ATTENDAIT. `diagnostics` nomme la cause là où
            # les étiquettes historiques (`rejete_mouvement`) ne disaient
            # que le symptôme : il distingue un rendu statique d'une caméra
            # qui mange le plan, ce qu'aucune chaîne de caractères ne
            # pouvait faire.
            #
            # `depuis_verdict()` et non `observer_clip()` : le verdict est
            # déjà calculé, et rappeler la sonde relancerait un
            # échantillonnage ffmpeg complet pour recalculer un nombre qu'on
            # tient.
            diagnostic_precis = _diagnostiquer(
                verdict, plan, i, duree_requise=duree_requise)

            if not duree_ok:
                # Le fournisseur a rendu un clip invalide ou plus court que
                # la durée allouée. `trim=duration=...` au montage ne peut
                # pas RALLONGER un clip trop court — laisser passer ça
                # produit une vidéo dont la piste vidéo s'arrête avant la
                # voix. Mesuré en production : 4,5 s de narration sans
                # image, sur exactement ce plan. L'argent est déjà dépensé
                # (`depense` le garde) ; on ne perd que le clip, pas l'épisode.
                log.info(
                    "Plan %d : API=SUCCESS FICHIER=%s DURÉE=%s ANIMATION=REJECTED "
                    "RAISON=%s", i, "VALID" if verdict.fichier_valide else "INVALID",
                    "TOO_SHORT" if verdict.fichier_valide else "N/A",
                    "clip_invalide" if not verdict.fichier_valide else "clip_too_short",
                )
                resultats.append(_repli(i, image, dossier, plan, vie_pour_le_reste,
                                        duree_clip_s, diagnostic="rejete_duree",
                                        cout=cout, cause=diagnostic_precis))
                continue

            if not verdict.mouvement_detecte:
                # Point critique de l'enquête run #66 : un clip peut être un
                # fichier vidéo valide, de la bonne durée, et pourtant
                # visuellement statique. « API 200 » et « fichier livré » ne
                # prouvent jamais qu'une image a réellement changé d'une
                # frame à l'autre — voir `verification_mouvement.py`.
                log.info(
                    "Plan %d : API=SUCCESS FICHIER=VALID DURÉE=VALID "
                    "MOUVEMENT=ABSENT ANIMATION=REJECTED RAISON=STATIC_CLIP "
                    "(diff. moyenne %.3f/255)", i, verdict.diff_moyenne,
                )
                resultats.append(_repli(i, image, dossier, plan, vie_pour_le_reste,
                                        duree_clip_s, diagnostic="rejete_mouvement",
                                        cout=cout, cause=diagnostic_precis))
                continue

            log.info(
                "Plan %d : API=SUCCESS FICHIER=VALID DURÉE=VALID "
                "MOUVEMENT=DETECTED ANIMATION=ACCEPTED (diff. moyenne %.3f/255)",
                i, verdict.diff_moyenne,
            )
            resultats.append(PlanAnime(i, destination, True, "modele", cout,
                                       diagnostic="mouvement_confirme"))
        else:
            # Deux raisons TRÈS différentes de ne pas avoir payé, et les
            # confondre effacerait l'information la plus utile :
            #   · `non_elu`          — le plan n'était pas assez important,
            #                          ou le budget ne suivait pas ;
            #   · `strategie_locale` — le plan était élu, mais rien de ce
            #                          qu'il demande n'exige un modèle
            #                          génératif. La parallaxe le rend
            #                          gratuitement ET à coup sûr.
            # Le second est un SUCCÈS d'arbitrage, pas un renoncement.
            resultats.append(_repli(
                i, image, dossier, plan, vie_pour_le_reste, duree_clip_s,
                diagnostic="strategie_locale" if i in ecartes else "non_elu"))

    reussis = sum(1 for r in resultats if r.anime)
    if combien and not reussis:
        # Un échec d'animation est délibérément rattrapé en image fixe pour ne
        # pas perdre l'épisode. Sans ce cri, la vidéo sort complète et muette
        # sur le sujet : c'est exactement comme ça qu'un identifiant de modèle
        # périmé a produit des épisodes sans animation pendant plusieurs
        # productions, sans que rien ne le signale.
        log.error(
            "AUCUN plan animé : les %d tentatives ont toutes échoué, l'épisode "
            "sort en images fixes. Vérifie que l'identifiant du modèle "
            "d'animation dans modeles.yaml correspond à un endpoint publié "
            "par le fournisseur (voir les avertissements ci-dessus).", combien,
        )
    # Répartition par méthode+diagnostic — remplace le seul « X animés » qui
    # mélangeait un vrai clip modèle et un repli local sous `anime=True`
    # (voir l'enquête run #66). C'est la réponse factuelle à « combien de
    # plans ont réellement un mouvement modèle confirmé », pas seulement
    # « combien de requêtes ont réussi ».
    mouvement_confirme = sum(1 for r in resultats if r.diagnostic == "mouvement_confirme")
    parallaxe = sum(1 for r in resultats if r.methode == "vie")
    image_fixe = sum(1 for r in resultats if r.methode == "camera")
    # `perdu` : de l'argent réellement dépensé pour un clip finalement
    # écarté. Journalisé à part parce que c'est la seule dépense du système
    # qui n'achète rien — la voir, c'est pouvoir décider si le modèle vaut
    # encore son prix. Il est bien compté dans `depense` ET dans le total
    # de l'épisode (voir `_repli(cout=...)`), jamais silencieux.
    perdu = sum(r.cout for r in resultats if r.methode != "modele")
    # « %d sur %d » avec (len(resultats), combien) s'affichait à l'envers —
    # « 6 plan(s) sur 4 » en production (run #77), les deux nombres ne
    # décrivant pas le même ensemble : `combien` compte les plans ÉLUS pour
    # l'appel payant, `resultats` TOUS les plans. Nommés séparément plutôt
    # que remis dans l'ordre : le lecteur ne peut pas deviner lequel des deux
    # est lequel.
    log.info(
        "Animation terminée : %d plan(s) traités, %d tenté(s) au modèle — "
        "mouvement modèle confirmé : %d · parallaxe locale : %d · "
        "image fixe : %d · %.3f € dépensés (dont %.3f € sur des clips écartés)",
        len(resultats), combien, mouvement_confirme, parallaxe, image_fixe,
        depense, perdu,
    )
    _enregistrer_experience(resultats, plans, job_id=job_id, profil=profil)
    return resultats


# ── Ce que chaque tentative a réellement donné ──────────────────────────

# `PlanAnime.diagnostic` porte déjà le POURQUOI de chaque plan. Cette table
# le traduit en (stratégie réellement employée, mode d'échec, verdict) — les
# trois choses dont `ExperienceMemory` a besoin pour qu'un routage empirique
# soit possible un jour.
#
# Le piège à éviter, et c'est tout l'enjeu : un plan qui n'a JAMAIS été tenté
# au modèle (`non_elu`, `hors_portee`) ne doit pas être enregistré comme un
# échec de `DIRECT_I2V`. Ce serait inventer des échecs à une stratégie qui
# n'a rien tenté, et le taux de réussite qu'on en tirerait serait faux — dans
# le sens qui coûte le plus cher, celui qui fait renoncer à ce qui marche.
_LECTURE_DIAGNOSTIC: dict[str, tuple[str, ModeEchec | None, str]] = {
    "mouvement_confirme": ("modele", None, "PASS"),
    "rejete_mouvement": ("modele", ModeEchec.RENDU_STATIQUE, "FAIL"),
    "rejete_duree": ("modele", ModeEchec.DUREE_INCORRECTE, "FAIL"),
    # Une erreur de fournisseur n'est pas un mode d'échec du RENDU : le
    # modèle n'a rien produit qu'on puisse juger. `UNKNOWN` est exact, et le
    # confondre avec un rendu statique fausserait la taxonomie.
    "timeout": ("modele", ModeEchec.INCONNU, "FAIL"),
    "erreur_appel": ("modele", ModeEchec.INCONNU, "FAIL"),
    # Jamais tenté au modèle : c'est le REPLI qui a produit le plan, et c'est
    # lui qu'on enregistre.
    "hors_portee": ("repli", None, "PASS"),
    "non_elu": ("repli", None, "PASS"),
    # Élu, mais le graphe a jugé qu'aucun modèle génératif n'était nécessaire.
    # Une réussite d'arbitrage : le plan a été rendu, gratuitement, par la
    # stratégie qui savait le faire.
    "strategie_locale": ("repli", None, "PASS"),
}

_STRATEGIE_PAR_METHODE = {
    "modele": Strategie.DIRECT_I2V,
    "vie": Strategie.DEUX_ET_DEMI_D,
    "camera": Strategie.PROCEDURAL,
}

_MODELE_LOCAL = {
    "vie": "local/parallaxe",
    "camera": "local/montage",
}


def _enregistrer_experience(resultats: list[PlanAnime], plans: list[dict],
                            *, job_id: str | None, profil: str) -> None:
    """Consigne une ligne par TENTATIVE — la donnée du routage empirique.

    Sans `job_id`, rien n'est écrit : les démonstrations et les outils
    n'ont pas de job, et leurs résultats ne décrivent pas une production
    réelle. Les compter fausserait les statistiques avec des cas de test.

    N'interrompt JAMAIS la production : une mémoire d'expérience est un
    instrument de mesure, pas une étape du rendu. Perdre une ligne coûte
    une observation ; perdre l'épisode coûte la vidéo.
    """
    if not job_id:
        return

    try:
        modele_video = registre().resoudre(
            "animation", profil=profil, repli_si_cle_absente=True).modele.id
    except ErreurPdz:
        modele_video = ""

    memoire = ExperienceMemory()
    for resultat in resultats:
        _, mode, verdict = _LECTURE_DIAGNOSTIC.get(
            resultat.diagnostic, ("repli", None, ""))

        # Le diagnostic PRÉCIS l'emporte sur l'étiquette quand il existe :
        # `rejete_mouvement` ne dit que le symptôme, `CAMERA_DOMINANT` dit
        # la cause. C'est cette distinction que le routage empirique lira
        # un jour — deux causes opposées sous une même étiquette rendraient
        # la statistique inexploitable.
        if resultat.cause is not None:
            mode = resultat.cause.mode

        try:
            memoire.enregistrer(ExperienceRecord(
                job_id=job_id,
                shot_id=f"shot_{resultat.index:03d}",
                strategie=_STRATEGIE_PAR_METHODE.get(resultat.methode),
                backend="fal" if resultat.methode == "modele" else "local",
                modele=(modele_video if resultat.methode == "modele"
                        else _MODELE_LOCAL.get(resultat.methode, "")),
                fournisseur="fal" if resultat.methode == "modele" else "local",
                capacites_requises=("image_to_video",) if resultat.methode == "modele" else (),
                cout_reel_eur=resultat.cout,
                duree_demandee_s=float(plans[resultat.index].get("duree_s") or 0)
                if resultat.index < len(plans) else 0.0,
                diagnostic=mode,
                resultat=verdict,
                # `certitude` reste INCONNU par défaut : le verdict vient
                # d'une sonde de mouvement, qui mesure des pixels et non la
                # réussite narrative du plan. Le déclarer FAIT reviendrait à
                # confondre « ça bouge » et « ça montre ce qu'il fallait ».
                certitude=Certitude.HEURISTIQUE if verdict else Certitude.INCONNU,
            ))
        except Exception as e:  # noqa: BLE001 - voir la docstring
            log.warning("Expérience du plan %d non enregistrée : %s",
                        resultat.index, e)


def _filtrer_par_strategie(elus: list[int], plans: list[dict], images: list[Path],
                           *, budget_restant: float,
                           profil: str) -> tuple[set[int], dict[int, str]]:
    """Parmi les plans ÉLUS, lesquels méritent vraiment le modèle payant ?

    `noter()` classe les plans par ce que l'animation leur apporterait — c'est
    une question narrative, et il y répond bien. Le graphe de stratégies
    répond à une autre question, technique : **ce que ce plan demande, le
    modèle payant est-il seul à savoir le rendre ?**

    Les deux sont nécessaires, et leur ordre compte. Un plan peut porter
    l'épisode (note élevée) et n'attendre qu'un mouvement d'ambiance — que la
    parallaxe locale rend GRATUITEMENT et à coup sûr, là où le modèle rend
    0,23 € d'espérance. Le run #66 a mesuré exactement ce cas : un clip payé,
    valide, de la bonne durée, et parfaitement statique.

    Ce filtre ne remplace donc pas l'élection, il l'affine — et il ne peut
    qu'écarter, jamais ajouter : un plan non élu reste non élu.
    """
    from pdz.strategies import ContexteRendu, choisir

    retenus: set[int] = set()
    ecartes: dict[int, str] = {}

    for index in elus:
        plan = plans[index]
        # Sans mouvement décidé par ShotPromptWriter, il n'y a rien qu'un
        # modèle génératif soit seul à savoir rendre. `""` mène au gratuit,
        # ce qui est le comportement voulu — payer pour un mouvement que
        # personne n'a demandé serait le pire des deux mondes.
        attendu = _mouvement_attendu(plan)

        try:
            retenue, pourquoi = choisir(ContexteRendu(
                shot_id=f"shot_{index:03d}",
                image=images[index],
                destination=images[index].with_suffix(".mp4"),
                duree_s=float(plan.get("duree_s") or 0),
                profil=profil,
                budget_restant_eur=budget_restant,
                importance=_importance(plan, index),
                mouvement_attendu=attendu,
                index=index,
            ))
        except Exception as e:  # noqa: BLE001
            # Le graphe est un arbitre, pas un passage obligé : s'il échoue,
            # on retombe sur le comportement historique (tenter le modèle)
            # plutôt que de priver l'épisode d'animation.
            log.warning("Stratégie indécidable pour le plan %d (%s) : "
                        "le modèle est tenté comme avant", index, e)
            retenus.add(index)
            continue

        if retenue.strategie is Strategie.DIRECT_I2V:
            retenus.add(index)
        else:
            ecartes[index] = pourquoi

    return retenus, ecartes


def _mouvement_attendu(plan: dict) -> str:
    """`"sujet"` | `"ambiance"` | `"camera"` | `""` — ce que le plan EXIGE.

    Même règle que `pdz.scenes.PlanCompile.mouvement_attendu`, appliquée au
    `dict` que reçoit `animer()`. L'ordre n'est pas arbitraire : un plan qui
    demande un mouvement de sujet ET un pan de caméra reste avant tout un
    plan de sujet — c'est ce que la parallaxe ne saura pas rendre, donc ce
    qui décide.
    """
    if (plan.get("mouvement_sujet") or "").strip():
        return "sujet"
    if (plan.get("mouvement_environnement") or "").strip():
        return "ambiance"
    if (plan.get("mouvement_camera") or "") not in ("", "fixe"):
        return "camera"
    return ""


def _importance(plan: dict, index: int) -> float:
    """Ce que ce plan pèse dans le récit, entre 0 et 1.

    Reprend les critères de `noter()` — mêmes signaux, même ordre de force —
    mais normalisés, parce que le graphe de stratégies raisonne en euros et
    a besoin d'une valeur comparable d'un épisode à l'autre. Les garder
    séparés est délibéré : `noter()` classe DANS un épisode, `_importance`
    situe un plan dans l'absolu.
    """
    score = 0.45 if index == 0 else 0.0
    if plan.get("relance"):
        score += 0.25
    if plan.get("fonction"):
        score += 0.15
    if plan.get("emotion") in ("colere", "surprise", "peur"):
        score += 0.20
    if (plan.get("intensite_mouvement") or "") == "fort":
        score += 0.15
    return min(1.0, score)


# ── Réparer : changer la cause probable, pas relancer ───────────────────

# Ce que ce module sait appliquer DÉTERMINISTEMENT, sans rappeler un modèle
# d'écriture. Deux corrections, portant sur des champs que
# `_prompt_mouvement()` lit déjà — c'est ce qui les rend exécutables ici.
#
# Les autres branches du compilateur de réparation (`LOCAL_REPAIR`,
# `MODEL_FIX`, `DECOMPOSITION`, `ANCHOR_FIX`) sont VRAIES mais pas encore
# exécutables : elles demandent un masque, un second fournisseur, un
# redécoupage. Les déclarer applicables les ferait choisir puis échouer en
# silence, ce qui est pire que de ne pas les proposer.
_REPARATIONS_APPLICABLES = (
    TypeReparation.AJUSTER_MOUVEMENT,
    TypeReparation.AJUSTER_CAMERA,
)


def _amplifier_le_mouvement(plan: dict) -> dict:
    """`MOTION_FIX` — demander explicitement plus de mouvement.

    `intensite_mouvement = "fort"` ajoute « clearly visible, unmistakable
    motion throughout » au prompt compilé (voir `PHRASES_INTENSITE`). C'est
    la seule correction de mouvement applicable sans rappeler un modèle
    d'écriture — et elle vise exactement la cause d'un rendu resté statique.
    """
    plan["intensite_mouvement"] = "fort"
    return plan


def _verrouiller_la_camera(plan: dict) -> dict:
    """`CAMERA_FIX` — rendre le sujet lisible en immobilisant le cadre.

    Sur un `CAMERA_DOMINANT`, du mouvement existe mais ce n'est pas celui du
    sujet. Verrouiller la caméra retire au modèle la façon la plus facile de
    « bouger » sans rien montrer.

    Reste une INTENTION, pas une garantie : l'adaptateur n'envoie aucun
    paramètre de caméra, seulement du texte — voir
    `ControleCamera.TEXTE_SEULEMENT`. Un second échec sur le même plan sera
    un désaccord intention/résultat, pas un bug de paramétrage.
    """
    plan["mouvement_camera"] = "fixe"
    return plan


_CORRECTIONS = {
    TypeReparation.AJUSTER_MOUVEMENT: _amplifier_le_mouvement,
    TypeReparation.AJUSTER_CAMERA: _verrouiller_la_camera,
}


def _reparer(diagnostic, plan: dict, *, tentative: int,
             deja_tentees: tuple, budget_restant: float,
             tentatives_max: int = 2):
    """(plan corrigé, type appliqué, raison) — ou `(None, None, "")`.

    Rend `None` dans tous les cas où réparer serait déraisonnable, et chacun
    pour une raison distincte :

      · aucun diagnostic           — rien n'a échoué, il n'y a rien à réparer ;
      · diagnostic non actionnable — réparer sur une hypothèse à pile ou face
                                     coûte plus que le défaut lui-même ;
      · tentatives épuisées        — le plafond existe pour que la réparation
                                     ne coûte jamais plus que le plan ne vaut ;
      · branche non applicable     — voir `_REPARATIONS_APPLICABLES` ;
      · budget insuffisant         — un second rendu se paie comme le premier ;
      · **correction sans effet**  — voir plus bas.

    `tentatives_max = 2` : un seul essai de réparation. Le modèle coûte
    0,23 € le clip de 5 s pour un plafond de 0,60 € par vidéo — deux
    réparations sur un même plan mangeraient l'épisode entier.
    """
    if diagnostic is None or not diagnostic.actionnable:
        return None, None, ""
    if tentative >= tentatives_max:
        return None, None, ""
    # Un appel refusé pour budget est un appel qu'on n'aurait pas dû tenter :
    # le vérifier ici plutôt que de le découvrir chez le fournisseur.
    if budget_restant <= 0:
        return None, None, ""

    plan_repare = repair.compiler(
        diagnostic, tentative=tentative, tentatives_max=tentatives_max,
        deja_tentees=deja_tentees, budget_restant_eur=budget_restant,
    )
    if plan_repare.choisie not in _REPARATIONS_APPLICABLES:
        return None, None, ""

    corrige = _CORRECTIONS[plan_repare.choisie](dict(plan))

    # LE garde-fou. Une correction qui laisse le plan identique est une
    # relance déguisée : un second rendu, au même prix, avec la même cause
    # probable. C'est précisément ce que cette architecture interdit, et
    # aucune vérification en amont ne peut le garantir — seul le résultat
    # de la correction le dit.
    if corrige == plan:
        log.info("Réparation %s sans effet sur ce plan : abandon plutôt "
                 "qu'une relance à l'identique", plan_repare.choisie.value)
        return None, None, ""

    return corrige, plan_repare.choisie, plan_repare.raison


def _diagnostiquer(verdict, plan: dict, index: int, *, duree_requise: float):
    """Le rapport d'observation, confronté à ce que le plan attendait.

    Rend `None` quand rien ne cloche — un résultat, pas une absence.

    L'attendu est reconstruit ici à partir du plan plutôt que reçu tout
    fait : `animer()` reçoit des `dict`, pas des contrats, et remonter
    jusqu'au `PlanCompile` demanderait de changer sa signature — ce qui
    touche `episode.py`. Le branchement complet viendra avec l'orchestration ;
    en attendant, ceci nomme déjà correctement les causes.
    """
    from pdz.contracts import ObservationReport
    from pdz.diagnostics import Attendu, diagnostiquer
    from pdz.observation import depuis_verdict

    camera_verrouillee = (plan.get("mouvement_camera") or "") in ("", "fixe")
    attend_un_sujet = bool((plan.get("mouvement_sujet") or "").strip()
                           or plan.get("intensite_mouvement"))

    rapport = ObservationReport(
        id=f"observation_shot_{index:03d}", shot_id=f"shot_{index:03d}",
        artefact="",
        mesures=depuis_verdict(
            verdict,
            attendu="mouvement perceptible" if attend_un_sujet else "",
            duree_requise=duree_requise, tolerance_s=TOLERANCE_DUREE_S),
    )
    return diagnostiquer(
        Attendu(
            shot_id=f"shot_{index:03d}",
            sujet_doit_bouger=attend_un_sujet,
            camera_doit_bouger=not camera_verrouillee,
            duree_s=duree_requise,
            # La méprise n'est possible que si la caméra a le DROIT de
            # bouger : c'est alors qu'un mouvement de caméra peut être pris
            # pour celui du sujet. Sur une caméra verrouillée, il n'y a rien
            # à confondre — et déclarer la confusion y menait à « verrouiller
            # la caméra », une réparation sans aucun effet.
            confusions_interdites=() if camera_verrouillee else ("camera_only_motion",),
            importance=0.9 if index == 0 else 0.5,
        ),
        rapport,
    )


def _repli(index: int, image: Path, dossier: Path, plan: dict,
           avec_vie: bool, duree_clip_s: int, *, diagnostic: str = "",
           cout: float = 0.0, cause=None) -> PlanAnime:
    """Le plan n'est pas animé par un modèle : que fait-on à la place ?

    Deux niveaux, tous les deux gratuits. « vie » ajoute parallaxe et
    particules — c'est meilleur, mais ça produit un fichier vidéo et prend
    quelques secondes de CPU. « camera » laisse le montage appliquer son
    recadrage glissant, ce qui ne coûte rien du tout.

    `diagnostic` (voir `PlanAnime`) explique POURQUOI on est ici plutôt
    qu'avec un vrai clip modèle — porté par l'appelant, jamais recalculé.

    `cout` est l'argent DÉJÀ dépensé pour ce plan avant d'arriver ici : un
    clip payé puis rejeté (durée ou mouvement) a coûté malgré tout. Sans
    ce report, `episode.py` (`sum(a.cout for a in animes)`) n'additionnait
    que les clips ACCEPTÉS — mesuré sur le run #66 : 0,900 € réellement
    dépensés, 0,200 € comptabilisés, soit 78 % de la dépense d'animation
    invisible, alors que le plafond budgétaire est justement vérifié
    contre ce total. Le repli est gratuit ; ce qui l'a précédé ne l'est pas.

    `duree_clip_s` ne sert ici QUE de repli si `plan.duree_s` est absent —
    jamais de plafond. `vie.animer()` fabrique son clip image par image,
    sans aucune limite de durée technique, à la différence d'un modèle
    payant qui ne rend jamais plus que ce qu'on lui demande. Un plafond
    (`min(duree, duree_clip_s)`) était pourtant appliqué ici : sur un
    épisode réel (#57) où plusieurs plans duraient plus que
    `DUREE_CLIP_S` (5 s), leur repli local était tronqué à 5 s pour de
    bon — l'écart cumulé (6,3 s sur 5 plans) a fait échouer la
    vérification finale de durée (`coherence_duree`), qui a fait exactement
    son travail en refusant de livrer une vidéo silencieuse sur la fin.
    """
    # « vie » et « camera » ne sont pas deux bricolages : ce sont deux
    # STRATÉGIES, et elles portent enfin leur nom (PHASE 8). `TWO_POINT_FIVE_D`
    # et `PROCEDURAL` exécutent exactement ce que ce code faisait — le repli
    # de l'une vers l'autre en cas d'échec compris. Le comportement est
    # inchangé ; ce qui change, c'est qu'il est désormais nommé, comparable
    # et remplaçable.
    from pdz.strategies import ContexteRendu, StrategieProcedurale, StrategieTwoPointFiveD

    duree = float(plan.get("duree_s") or 0) or float(duree_clip_s)
    contexte = ContexteRendu(
        shot_id=str(index), image=image,
        destination=dossier / f"vie_{index:03d}.mp4",
        duree_s=duree, index=index,
    )

    strategie = StrategieTwoPointFiveD() if avec_vie else StrategieProcedurale()
    resultat = strategie.executer(contexte)

    if not resultat.clip_produit:
        # `PROCEDURAL` : rien n'est fabriqué ici, c'est le montage qui
        # appliquera le recadrage glissant.
        return PlanAnime(index, image, False, "camera", cout,
                         diagnostic=diagnostic, cause=cause)

    return PlanAnime(index, resultat.fichier, True, "vie", cout,
                     diagnostic=diagnostic, cause=cause)


def _prompt_mouvement(plan: dict, univers: Univers) -> str:
    """Ce qu'on demande au modèle vidéo de faire bouger.

    Ne fabrique plus rien lui-même : passe par le programme de mouvement
    (`pdz.production.motion_program`), qui sépare enfin l'INTENTION
    temporelle du plan (ce qui bouge, ce qui doit rester, ce qui est
    interdit — une donnée typée, exploitable par le diagnostic en aval) du
    TEXTE qu'on finit par envoyer au fournisseur. Cette fonction reste le
    point d'entrée historique : `animer()` et les tests l'appellent sans
    rien savoir de cette séparation.

    Ce que le prompt ne fait toujours PAS, mesuré comme nuisible :

    · **il ne redécrit pas la scène.** `action` (le prompt d'IMAGE, ~65 mots
      une fois enrichi par `fusionner()`) y était réinjecté, portant le
      prompt de mouvement à 119 mots — 2,6× le seuil de 45 que ce module
      documente lui-même. En image→vidéo, l'image d'entrée porte déjà la
      scène : la redécrire fait REFABRIQUER au lieu d'animer.
    · **il ne fige plus la caméra par défaut.** Le schéma demande au modèle
      de laisser `mouvement_camera` vide quand aucun mouvement n'apporte
      rien à ce plan ; traduire ce vide en « camera holds steady » revenait
      à instruire l'immobilité sur la majorité des plans. Vide ⇒ aucune
      phrase de caméra. Seul un choix EXPLICITE (« fixe » compris) en
      produit une.
    """
    return motion_program.compiler_prompt(
        motion_program.depuis_plan(plan, univers), univers)
