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
from pdz.univers import Univers

log = logging.getLogger(__name__)

# Durée d'un clip animé. Les modèles image→vidéo facturent à la seconde et
# n'acceptent en général que 5 ou 10 s ; 5 s couvre déjà deux plans montés.
DUREE_CLIP_S = 5

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


def noter(plans: list[dict]) -> list[Candidature]:
    """Classe les plans par ce que l'animation leur apporterait.

    Les critères, du plus fort au plus faible :
      · **le premier plan** — trois secondes décident de tout, et c'est le
        seul endroit où un mouvement réel se remarque à coup sûr ;
      · **l'émotion** — un visage qui bouge vaut surtout pour les émotions
        fortes ;
      · **la durée** — un plan de 3 s figé se voit, un plan de 1 s non ;
      · **les plans de réaction** sont pénalisés : l'immobilité y est un
        choix de montage valable, pas un défaut.
    """
    candidatures: list[Candidature] = []

    for i, plan in enumerate(plans):
        note, raisons = 0.0, []

        if i == 0:
            note += 3.0
            raisons.append("accroche")

        emotion = plan.get("emotion", "calme")
        if (bonus := EMOTIONS_FORTES.get(emotion, 0.0)):
            note += bonus
            raisons.append(emotion)

        duree = float(plan.get("duree_s", 0) or 0)
        if duree >= 3.0:
            note += 1.0
            raisons.append(f"{duree:.1f} s à l'écran")
        elif duree < 1.2:
            note -= 1.0
            raisons.append("trop court pour se voir")

        if plan.get("reaction"):
            note -= 0.8
            raisons.append("plan de réaction")

        if i == len(plans) - 1:
            note += 0.8
            raisons.append("dernier plan")

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
                resultats.append(_repli(i, image, dossier, plan, vie_pour_le_reste,
                                        duree_clip_s))
                continue

            depense += cout
            resultats.append(PlanAnime(i, destination, True, "modele", cout))
        else:
            resultats.append(_repli(i, image, dossier, plan, vie_pour_le_reste,
                                    duree_clip_s))

    log.info("Animation terminée : %.3f € dépensés", depense)
    return resultats


def _repli(index: int, image: Path, dossier: Path, plan: dict,
           avec_vie: bool, duree_clip_s: int) -> PlanAnime:
    """Le plan n'est pas animé par un modèle : que fait-on à la place ?

    Deux niveaux, tous les deux gratuits. « vie » ajoute parallaxe et
    particules — c'est meilleur, mais ça produit un fichier vidéo et prend
    quelques secondes de CPU. « camera » laisse le montage appliquer son
    recadrage glissant, ce qui ne coûte rien du tout.
    """
    if not avec_vie:
        return PlanAnime(index, image, False, "camera")

    from pdz.video.vie import Effets
    from pdz.video.vie import animer as animer_localement

    destination = dossier / f"vie_{index:03d}.mp4"
    duree = float(plan.get("duree_s") or 0) or float(duree_clip_s)
    try:
        animer_localement(
            image, min(duree, duree_clip_s), destination,
            effets=Effets(sens=1 if index % 2 == 0 else -1, graine=index),
        )
    except Exception as e:                        # PIL, ffmpeg, disque plein…
        log.warning("Effet « vie » impossible sur le plan %d : %s", index, e)
        return PlanAnime(index, image, False, "camera")

    return PlanAnime(index, destination, True, "vie")


def _prompt_mouvement(plan: dict, univers: Univers) -> str:
    """Ce qu'on demande au modèle vidéo de faire bouger.

    Court et concret. Les modèles image→vidéo réagissent mal aux longues
    descriptions : ils tentent alors de refabriquer la scène au lieu de
    l'animer, et le personnage change de tête en cours de clip.
    """
    action = (plan.get("action") or "").strip()
    emotion = plan.get("emotion", "calme")

    mouvement = {
        "colere": "the character shouts, shoulders heaving",
        "surprise": "the character recoils sharply, then freezes",
        "peur": "the character shrinks back, trembling slightly",
        "joie": "the character laughs, body bouncing",
        "tristesse": "the character looks down slowly",
        "mepris": "the character slowly turns their head away",
        "gene": "the character shifts weight, eyes darting sideways",
        "calme": "subtle idle motion, slight breathing, eyes blinking",
    }.get(emotion, "subtle idle motion")

    morceaux = [mouvement]
    if action:
        morceaux.append(action)
    morceaux.append("camera holds steady, character design stays identical")
    if univers.style.ambiance:
        morceaux.append(univers.style.ambiance)
    return ", ".join(morceaux)
