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

from pdz.ia import fal
from pdz.ia.registre import registre
from pdz.moteur.erreurs import ErreurPdz
from pdz.production import risque_prompt, verification_mouvement
from pdz.univers import Univers

log = logging.getLogger(__name__)

# Durée d'un clip animé DEMANDÉE au modèle. Les modèles image→vidéo
# facturent à la seconde. Remis à 5 (pas 10, comme ce matin) : l'enquête sur
# le run #66 a mesuré que demander 10 s produit EXACTEMENT le même résultat
# que demander 5 s — 4,84 s rendus dans les deux cas, identique à la mesure
# historique de l'épisode #57 — le paramètre `duration` n'a donc aucun effet
# constaté sur ce endpoint au-delà de ce plafond. Demander plus ne fait que
# doubler le coût par tentative pour rien.
DUREE_CLIP_S = 5

# Ce que le modèle rend RÉELLEMENT, mesuré (voir ci-dessus) — distinct de
# `DUREE_CLIP_S` (ce qu'on ENVOIE), qui n'a plus d'effet sur ce chiffre.
# C'est CE plafond qui doit décider si un plan mérite l'appel payant : un
# plan de 6 s a exactement la même chance de succès qu'on demande 5 ou 10 s
# au modèle, puisque le rendu réel plafonne ici quel que soit ce qu'on
# demande.
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


def noter(plans: list[dict]) -> list[Candidature]:
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
        if 3.0 <= duree <= DUREE_REELLE_MAX_S:
            note += 1.0
            raisons.append(f"{duree:.1f} s à l'écran, dans la capacité du modèle")
        elif duree > DUREE_REELLE_MAX_S:
            note -= 0.5
            raisons.append(
                f"{duree:.1f} s hors de portée du modèle (max ~{DUREE_REELLE_MAX_S:.1f} s)")
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
    cout_unitaire = res.modele.cout_unites(duree_clip_s, "seconde")
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
    combien, raison = combien_animer(len(plans), budget_restant, profil=profil,
                                     duree_clip_s=duree_clip_s)
    classement = noter(plans)
    elus = {c.index for c in classement[:combien]}

    log.info("Animation : %d plan(s) sur %d — %s", combien, len(plans), raison)
    for c in classement[:combien]:
        log.info("  · plan %d (note %.1f) : %s", c.index, c.note, c.raison)

    resultats: list[PlanAnime] = []
    depense = 0.0

    for i, (plan, image) in enumerate(zip(plans, images, strict=True)):
        if i in elus:
            destination = dossier / f"anime_{i:03d}.mp4"
            duree_requise = float(plan.get("duree_s") or 0)
            if duree_requise > DUREE_REELLE_MAX_S:
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
                    "repli direct.", i, duree_requise, DUREE_REELLE_MAX_S,
                )
                resultats.append(_repli(i, image, dossier, plan, vie_pour_le_reste,
                                        duree_clip_s, diagnostic="hors_portee"))
                continue
            reste = max(0.0, budget_restant - depense)
            try:
                _, cout = fal.animer_image(
                    image, _prompt_mouvement(plan, univers), destination,
                    duree_s=duree_clip_s, profil=profil,
                    budget_restant_pct=100.0 if reste > 0 else 0.0,
                    job_id=job_id, agent="animation",
                )
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
                                        cout=cout))
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
                                        cout=cout))
                continue

            log.info(
                "Plan %d : API=SUCCESS FICHIER=VALID DURÉE=VALID "
                "MOUVEMENT=DETECTED ANIMATION=ACCEPTED (diff. moyenne %.3f/255)",
                i, verdict.diff_moyenne,
            )
            resultats.append(PlanAnime(i, destination, True, "modele", cout,
                                       diagnostic="mouvement_confirme"))
        else:
            resultats.append(_repli(i, image, dossier, plan, vie_pour_le_reste,
                                    duree_clip_s, diagnostic="non_elu"))

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
    log.info(
        "Animation terminée : %d plan(s) sur %d — mouvement modèle confirmé : %d · "
        "parallaxe locale : %d · image fixe : %d · %.3f € dépensés (dont %.3f € "
        "sur des clips écartés)",
        len(resultats), combien, mouvement_confirme, parallaxe, image_fixe,
        depense, perdu,
    )
    return resultats


def _repli(index: int, image: Path, dossier: Path, plan: dict,
           avec_vie: bool, duree_clip_s: int, *, diagnostic: str = "",
           cout: float = 0.0) -> PlanAnime:
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
    if not avec_vie:
        return PlanAnime(index, image, False, "camera", cout, diagnostic=diagnostic)

    from pdz.video.vie import Effets
    from pdz.video.vie import animer as animer_localement

    destination = dossier / f"vie_{index:03d}.mp4"
    duree = float(plan.get("duree_s") or 0) or float(duree_clip_s)
    try:
        animer_localement(
            image, duree, destination,
            effets=Effets(sens=1 if index % 2 == 0 else -1, graine=index),
        )
    except Exception as e:                        # PIL, ffmpeg, disque plein…
        log.warning("Effet « vie » impossible sur le plan %d : %s", index, e)
        return PlanAnime(index, image, False, "camera", cout, diagnostic=diagnostic)

    return PlanAnime(index, destination, True, "vie", cout, diagnostic=diagnostic)


# Repli historique, gardé pour un job en cache d'avant plans@1.13.0, ou un
# plan où ShotPromptWriter n'a rien décidé de plus précis que l'émotion.
# Toujours filtré par `risque_prompt.purger_mouvement_interdit()` — ce
# vocabulaire, écrit pour un visage humain, a produit un clip mesuré
# statique sur un univers wireframe sans visage (enquête run #66).
_VOCABULAIRE_EMOTION = {
    "colere": "the character shouts, shoulders heaving",
    "surprise": "the character recoils sharply, then freezes",
    "peur": "the character shrinks back, trembling slightly",
    "joie": "the character laughs, body bouncing",
    "tristesse": "the character looks down slowly",
    "mepris": "the character slowly turns their head away",
    "gene": "the character shifts weight, eyes darting sideways",
    "calme": "subtle idle motion, slight breathing, eyes blinking",
}

# Vocabulaire fixe et court, comme `cadrage.PHRASES`/`cadrage.PHRASES_DISPOSITION`
# — ShotPromptWriter choisit une valeur, cette table la traduit en anglais.
_PHRASES_CAMERA = {
    "push_in_lent": "camera performs a slow forward push-in",
    "pull_back_lent": "camera performs a slow pull-back",
    "pan_lent": "camera pans slowly across the scene",
    "leger_tremblement": "subtle handheld camera vibration",
    "fixe": "camera holds steady",
}


def _prompt_mouvement(plan: dict, univers: Univers) -> str:
    """Ce qu'on demande au modèle vidéo de faire bouger.

    Compilé depuis les décisions de mouvement de ShotPromptWriter
    (`mouvement_sujet`/`mouvement_camera`/`mouvement_environnement`/
    `intensite_mouvement`, voir plans@1.13.0) — plus un dictionnaire fixe
    par émotion appliqué sans discernement à tous les plans. Le modèle qui
    a déjà lu le script entier sait, plan par plan, ce qui doit RÉELLEMENT
    évoluer ; un vocabulaire figé par émotion ne peut pas le savoir.

    Deux choses que ce prompt ne fait PLUS, mesurées comme nuisibles :

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
    sujet = (plan.get("mouvement_sujet") or "").strip()
    if not sujet:
        emotion = plan.get("emotion", "calme")
        sujet = _VOCABULAIRE_EMOTION.get(emotion, "subtle idle motion")

    morceaux = [sujet]

    if phrase_camera := _PHRASES_CAMERA.get(plan.get("mouvement_camera") or ""):
        morceaux.append(phrase_camera)
    morceaux.append("character design stays identical")

    if env := (plan.get("mouvement_environnement") or "").strip():
        morceaux.append(env)

    if plan.get("intensite_mouvement") == "fort":
        morceaux.append("clearly visible, unmistakable motion throughout")

    prompt = ", ".join(morceaux)

    registre = (plan.get("registre_visuel") or "").strip()
    if registre and registre.lower() not in prompt.lower():
        prompt = f"{prompt}, maintain style: {registre}"

    if univers.style.ambiance:
        prompt = f"{prompt}, {univers.style.ambiance}"

    return risque_prompt.purger_mouvement_interdit(prompt, univers)
