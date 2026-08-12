"""Fabrique les images de l'épisode — et surtout, garde les personnages **stables**.

C'est le problème n°1 des séries générées : à l'épisode 3, le personnage n'a
plus la même tête. Le spectateur ne saurait pas dire pourquoi, mais il ne
revient pas. Trois mécanismes s'en occupent ici, dans cet ordre :

  1. **La fiche de personnage.** Une image de référence est générée UNE fois
     par personnage, puis renvoyée à chaque plan comme image de départ. C'est
     ce qui pèse le plus lourd : sans elle, la description seule laisse encore
     dériver la couleur, la forme du visage, la coupe.
  2. **La graine fixe de l'univers.** Même graine → même patte graphique. Elle
     est dérivée du nom de l'univers, donc identique d'une machine à l'autre
     et d'un mois à l'autre.
  3. **L'apparence complète dans chaque prompt.** Jamais « Strawberina » —
     le modèle ne sait pas qui c'est. Toujours les 40 mots de description.

Le reste du module est du cache : une image déjà produite pour un prompt
identique n'est jamais repayée, même dans un autre épisode.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from pdz.config import config
from pdz.ia import images as ia_images
from pdz.moteur.erreurs import ErreurBudget, ErreurConfig
from pdz.production.storyboard import PlanScript
from pdz.univers import Personnage, Univers

log = logging.getLogger(__name__)

# Les émotions du script, traduites en indications **visuelles**. Écrire
# « angry » dans un prompt donne un visage vaguement contrarié ; décrire les
# sourcils et la bouche donne la colère. C'est la différence entre un
# personnage qui joue et un personnage qui pose.
EXPRESSIONS = {
    "colere": "furious expression, inner eyebrow ends angled down toward the nose, "
              "mouth open mid-shout, leaning forward",
    "surprise": "shocked expression, eyebrows raised high, eyes wide open, "
                "mouth in a small round O, head pulled back",
    "tristesse": "sad expression, inner eyebrow ends raised, eyes looking down, "
                 "mouth corners turned down, shoulders dropped",
    "joie": "delighted expression, eyes squeezed into happy arcs, wide open smile, "
            "head tilted back slightly",
    "mepris": "contemptuous expression, one eyebrow raised, eyelids half closed, "
              "one mouth corner pulled sideways, chin lifted",
    "peur": "frightened expression, inner eyebrow ends raised and pulled together, "
            "eyes very wide, mouth stretched thin, body recoiling",
    "calme": "calm neutral expression, relaxed eyebrows, steady gaze",
    "gene": "embarrassed expression, eyes glancing away, tight closed smile, "
            "shoulders slightly hunched",
}

# Une fiche de personnage se regarde de face, en pied, sur fond neutre : c'est
# ce qui en fait une référence exploitable. Une fiche prise dans une scène
# transmettrait aussi le décor et l'éclairage de cette scène à tous les plans.
GABARIT_FICHE = (
    "character reference sheet, single character standing facing the camera, "
    "full body, neutral pose, arms relaxed at the sides, plain flat "
    "light grey background, even neutral lighting, no props, no text"
)


@dataclass
class PlanImage:
    numero: int
    personnage: str
    prompt: str
    fichier: Path
    cout: float = 0.0
    depuis_cache: bool = False


@dataclass
class Planche:
    """Le résultat complet : les fiches et les plans."""

    fiches: dict[str, Path] = field(default_factory=dict)
    plans: list[PlanImage] = field(default_factory=list)
    cout: float = 0.0
    images_evitees: int = 0

    @property
    def fichiers(self) -> list[Path]:
        return [p.fichier for p in self.plans]

    def resume(self) -> str:
        eco = f" · {self.images_evitees} réutilisées du cache" if self.images_evitees else ""
        return (f"{len(self.fiches)} fiches · {len(self.plans)} plans · "
                f"{self.cout:.3f} €{eco}")


# ── Construction des prompts ─────────────────────────────────────────────

def prompt_fiche(personnage: Personnage, univers: Univers) -> str:
    """Le prompt de la planche de référence d'un personnage."""
    morceaux = [personnage.apparence.strip(), GABARIT_FICHE,
                univers.style.rendu.strip()]
    return ", ".join(m for m in morceaux if m)


def prompt_plan(personnage: Personnage, univers: Univers, *,
                action: str, emotion: str = "calme",
                decor: str = "", consignes: list[str] | None = None,
                fonction: str = "") -> str:
    """Le prompt d'un plan : qui, faisant quoi, où, avec quelle tête.

    L'ordre n'est pas indifférent. Les modèles d'image donnent plus de poids
    au début du prompt : le personnage passe donc en premier, le style en
    dernier. Inversé, on obtient de très belles images du mauvais personnage.

    En **narration**, il n'y a personne à l'écran : c'est une voix off sur
    des images de scène. Mettre l'apparence du narrateur en tête donnerait
    vingt portraits du même sujet là où il faut vingt scènes différentes.
    L'action prend donc la première place, et l'expression disparaît — un
    visage qu'on ne voit pas n'a pas d'émotion à jouer.

    `fonction` est le SHOT_FUNCTION écrit par le scénariste (`fonction_plan`
    dans le script) — pourquoi ce plan existe dans la mécanique d'attention,
    pas ce qu'il montre. Sans elle, ce champ était calculé puis jeté : capturé
    dans le storyboard, jamais lu par la génération d'image. Deux plans à la
    même action mais des fonctions différentes ("établit l'échelle du monde"
    vs "révèle un détail") doivent produire des prompts différents, sinon
    l'empreinte créative ne pèse sur rien de visible à l'écran.
    """
    if not univers.anime:
        morceaux = [action.strip()]
    else:
        morceaux = [
            personnage.apparence.strip(),
            EXPRESSIONS.get(emotion, EXPRESSIONS["calme"]),
            action.strip(),
        ]

    if fonction.strip():
        morceaux.append(f"shot chosen to: {fonction.strip()}")

    # Ce que l'univers s'interdit TOUJOURS passe juste après l'action,
    # avant le décor et le style — pas en fin de prompt. Mesuré à l'écran
    # sur techno-holo : la consigne « wireframe and transparent surfaces
    # only, never solid rendered characters » était bien présente (voir
    # test_les_consignes_de_lunivers_partent_dans_chaque_image), mais
    # reléguée en position ~19 d'un prompt à 28 segments — trop loin pour
    # peser face à une action qui décrit un humain. Le personnage rendu
    # était plein, pas filaire, et changeait de tenue d'un plan à l'autre.
    morceaux += [c.strip() for c in univers.style.consignes_image]

    if decor and (d := univers.decor(decor)):
        morceaux.append(d.description.strip())
    elif univers.anime and univers.decors:
        # Ce repli n'a de sens que pour une série à personnages : parmi ses
        # décors, il y en a toujours un de pertinent, l'histoire s'y déroule.
        # En narration, les décors ne sont qu'une poignée de scènes
        # génériques (ville, réseau...) qui ne couvrent pas un sujet libre —
        # imposer quand même le premier produisait systématiquement une
        # ville, quel que soit le sujet. Mesuré à l'écran : un plan sur
        # « un homme allongé regarde son téléphone » recevait la
        # description de la ville filaire, qui a fini par dominer l'image.
        # L'action seule, déjà libre en narration, s'en sort mieux.
        morceaux.append(univers.decors[0].description.strip())

    morceaux.append(univers.style.rendu.strip())
    if univers.style.eclairage:
        morceaux.append(univers.style.eclairage.strip())
    # Mesurées sur une vidéo de référence (contraste, grain) : s'ajoutent
    # à celles de l'univers, ne les remplacent pas.
    morceaux += [c.strip() for c in (consignes or [])]
    morceaux.append("vertical 9:16 composition")

    return ", ".join(m for m in morceaux if m)


def graine_du_plan(univers: Univers, prompt: str) -> int | None:
    """La graine à utiliser pour ce plan précis.

    Sur une **série à personnages**, la graine de l'univers est fixe : c'est
    l'un des trois mécanismes qui gardent la même patte graphique d'un plan
    à l'autre (voir l'en-tête du module).

    Sur une **narration**, cette même graine appliquée à vingt scènes
    différentes les ramène toutes à la même image — mesuré en conditions
    réelles : une ville filaire identique pendant tout l'épisode, alors que
    le script décrivait des scènes variées. On la fait donc varier par plan,
    en la dérivant du prompt : deux exécutions du même plan gardent la même
    image (le cache continue de servir), deux plans différents cessent de se
    ressembler.
    """
    base = univers.style.seed
    if base is None or univers.anime:
        return base
    variation = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
    return (base + variation) % 2_147_483_647


def _empreinte(prompt: str, seed: int | None, reference: Path | None) -> str:
    """Empreinte d'une image : le prompt, la graine, et la référence utilisée.

    La référence entre par son **contenu** : régénérer la fiche d'un
    personnage doit invalider tous ses plans, sinon on mélange deux versions
    du même personnage dans un même épisode.
    """
    brut = f"{prompt}|{seed}"
    if reference is not None and reference.exists():
        brut += "|" + hashlib.sha256(reference.read_bytes()).hexdigest()[:16]
    return hashlib.sha256(brut.encode()).hexdigest()[:24]


# ── Production ───────────────────────────────────────────────────────────

def _produire(prompt: str, destination: Path, *, univers: Univers,
              reference: Path | None, profil: str, budget_restant_pct: float,
              cache: bool, job_id: str | None) -> tuple[float, bool]:
    """Génère une image, ou la reprend du cache. Renvoie (coût, depuis_cache)."""
    dossier_cache = config().dossier_cache / "images"
    dossier_cache.mkdir(parents=True, exist_ok=True)
    graine = graine_du_plan(univers, prompt)
    garde = dossier_cache / f"{_empreinte(prompt, graine, reference)}.jpg"

    if cache and garde.exists() and garde.stat().st_size > 1000:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(garde, destination)
        return 0.0, True

    _, cout = ia_images.generer_image(
        prompt, destination,
        image_reference=reference,
        seed=graine,
        profil=profil,
        budget_restant_pct=budget_restant_pct,
        job_id=job_id,
        agent="directeur_image",
    )
    if cache:
        shutil.copyfile(destination, garde)
    return cout, False


def fiches(univers: Univers, dossier: Path, *, profil: str = "equilibre",
           budget_restant_pct: float = 100.0, cache: bool = True,
           job_id: str | None = None,
           chemin_univers: Path | None = None) -> dict[str, Path]:
    """Génère la planche de référence de chaque personnage. Une fois pour toutes.

    Si `chemin_univers` est donné, les fiches sont écrites dans l'univers :
    les épisodes suivants les retrouvent sans rien regénérer, y compris après
    une purge du cache.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    resultat: dict[str, Path] = {}
    cout_total = 0.0

    # En narration, la fiche n'a pas d'objet : personne n'apparaît à l'écran.
    # Pire, elle serait renvoyée comme image de départ à chaque plan et
    # rendrait les vingt scènes identiques — exactement l'inverse du but.
    if not univers.anime:
        log.info("Format « %s » : pas de fiche de personnage à produire.",
                 univers.format.value)
        return resultat

    for perso in univers.personnages:
        if perso.fiche_image and Path(perso.fiche_image).exists():
            resultat[perso.id] = Path(perso.fiche_image)
            log.info("Fiche %s : déjà là (%s)", perso.nom, Path(perso.fiche_image).name)
            continue

        destination = dossier / f"fiche_{perso.id}.jpg"
        cout, du_cache = _produire(
            prompt_fiche(perso, univers), destination,
            univers=univers, reference=None, profil=profil,
            budget_restant_pct=budget_restant_pct, cache=cache, job_id=job_id,
        )
        cout_total += cout
        perso.fiche_image = destination
        resultat[perso.id] = destination
        log.info("Fiche %s → %s (%.3f €%s)", perso.nom, destination.name, cout,
                 ", du cache" if du_cache else "")

    if chemin_univers is not None:
        univers.sauver(chemin_univers)
    log.info("Fiches de personnages : %.3f €", cout_total)
    return resultat


def fabriquer(plans: list[PlanScript], univers: Univers, dossier: Path, *,
              consignes: list[str] | None = None,
              profil: str = "equilibre",
              budget_max: float | None = None,
              cache: bool = True,
              job_id: str | None = None,
              chemin_univers: Path | None = None) -> Planche:
    """Produit une image par plan du storyboard.

    On part du storyboard et non des répliques : le découpage en plans est
    décidé à un seul endroit (`pdz.production.storyboard`). Le refaire ici
    donnerait un jour un plan d'écart avec le montage, et des images décalées
    d'un cran sur tout l'épisode.
    """
    if not plans:
        raise ErreurConfig("Aucun plan : rien à illustrer.")

    plafond = budget_max if budget_max is not None else config().budget_max_par_video_eur
    dossier.mkdir(parents=True, exist_ok=True)

    planche = Planche()
    planche.fiches = fiches(
        univers, dossier, profil=profil, cache=cache, job_id=job_id,
        chemin_univers=chemin_univers,
    )

    for plan in plans:
        perso = univers.personnage(plan.personnage)
        if perso is None:
            raise ErreurConfig(
                f"Plan {plan.numero} : personnage « {plan.personnage} » "
                f"absent de l'univers « {univers.nom} »."
            )

        if planche.cout >= plafond:
            raise ErreurBudget(
                f"Plafond de {plafond:.2f} € atteint après {len(planche.plans)} "
                "plans. Relancer la commande reprendra ici — les plans déjà "
                "produits sont en cache et ne seront pas repayés."
            )

        prompt = prompt_plan(perso, univers, action=plan.action,
                             emotion=plan.emotion, decor=plan.decor,
                             consignes=consignes, fonction=plan.fonction)
        destination = dossier / f"plan_{plan.numero:03d}.jpg"
        reste_pct = max(0.0, (plafond - planche.cout) / max(1e-6, plafond) * 100)

        cout, du_cache = _produire(
            prompt, destination, univers=univers,
            reference=planche.fiches.get(perso.id), profil=profil,
            budget_restant_pct=reste_pct, cache=cache, job_id=job_id,
        )
        planche.plans.append(PlanImage(
            numero=plan.numero, personnage=perso.id, prompt=prompt,
            fichier=destination, cout=cout, depuis_cache=du_cache,
        ))
        planche.cout += cout
        planche.images_evitees += int(du_cache)

    log.info("Images : %s", planche.resume())
    return planche
