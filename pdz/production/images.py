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

import asyncio
import hashlib
import logging
import os
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path

from pdz.config import config
from pdz.contracts.execution import ExecutionPlan, NoeudExecution
from pdz.execution import executer
from pdz.ia import images as ia_images
from pdz.moteur.erreurs import ErreurBudget, ErreurConfig
from pdz.production import contrat_visuel, decision_visuelle, risque_prompt
from pdz.production.cadrage import phrase as phrase_de_cadrage
from pdz.production.contrat_visuel import ContratVisuel
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
    contrat: ContratVisuel | None = None


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
                fonction: str = "", cadrage: str = "",
                registre_visuel: str = "") -> str:
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

    `cadrage` (voir `pdz.production.cadrage`) vient d'un vocabulaire fixe
    écrit par ShotPromptWriter — la formule anglaise correspondante est
    ajoutée ici, juste après l'action. ShotPromptWriter décrit déjà le
    cadrage en prose dans `action`, mais rien ne garantissait qu'un
    mot-clé de cadrage fiable atteigne vraiment le modèle d'image ; cette
    formule le garantit en plus du texte libre, sans jamais le remplacer.

    `registre_visuel` (écrit par ShotPromptWriter, voir plans@1.7.0) répond
    à un problème différent de `cadrage` : la PRÉSENCE d'un objet dans le
    prompt ne garantit pas le bon REGISTRE visuel. Mesuré à l'écran : un
    prompt sur des câbles sous-marins contenait bien le mot « océans », et
    Flux a quand même produit une carte géographique réaliste en couleur —
    pas une scène wireframe. Ajouter l'objet manquant ne change rien au
    registre choisi par le modèle ; il faut l'imposer explicitement, tout
    aussi tôt que le cadrage.
    """
    if not univers.anime:
        morceaux = [action.strip()]
    else:
        morceaux = [
            personnage.apparence.strip(),
            EXPRESSIONS.get(emotion, EXPRESSIONS["calme"]),
            action.strip(),
        ]

    if phrase := phrase_de_cadrage(cadrage):
        morceaux.append(phrase)

    if registre_visuel.strip():
        morceaux.append(registre_visuel.strip())

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


def prompt_plan_depuis_contrat(contrat: ContratVisuel, univers: Univers, *,
                               consignes: list[str] | None = None) -> str:
    """Compile un `ContratVisuel` (voir `pdz.production.contrat_visuel`) en
    prompt — un simple passe-plat vers `prompt_plan()`, qui reste l'unique
    implémentation de l'assemblage, inchangée. N'existe que pour donner une
    entrée typée et documentée au même résultat."""
    perso = univers.personnage(contrat.qui)
    return prompt_plan(
        perso, univers, action=contrat.quoi, emotion=contrat.emotion,
        decor=contrat.ou_id, consignes=consignes,
        fonction=contrat.fonction, cadrage=contrat.cadrage,
        registre_visuel=contrat.registre_visuel_plan,
    )


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
        # Écriture puis renommage, et non une copie directe vers `garde` :
        # depuis que les plans sont produits en parallèle, deux plans au
        # prompt identique visent la MÊME entrée de cache. Une copie
        # concurrente y laisserait un fichier tronqué — assez gros pour
        # passer le seuil de 1000 octets plus haut, donc réutilisé comme
        # une image valide. `os.replace` est atomique sur le même système
        # de fichiers : le lecteur voit l'ancienne entrée ou la nouvelle,
        # jamais une moitié.
        provisoire = garde.with_name(f"{garde.stem}.{os.getpid()}-"
                                     f"{threading.get_ident()}.tmp")
        shutil.copyfile(destination, provisoire)
        os.replace(provisoire, garde)
    return cout, False


def regenerer(prompt: str, destination: Path, *, univers: Univers,
             reference: Path | None, profil: str, budget_restant_pct: float,
             job_id: str | None) -> tuple[float, bool]:
    """Regénère une image dont la QA visuelle a signalé un écart réel.

    Jamais depuis le cache : le prompt vient d'être corrigé exprès pour
    différer de celui qui a produit l'image jugée en écart — le cache est
    keyé sur le texte du prompt, donc un prompt différent le manque de
    toute façon, mais `cache=False` rend l'intention explicite plutôt que
    de compter sur cet effet de bord.
    """
    return _produire(prompt, destination, univers=univers, reference=reference,
                     profil=profil, budget_restant_pct=budget_restant_pct,
                     cache=False, job_id=job_id)


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


@dataclass
class _Travail:
    """Tout ce qu'un plan demande AVANT que le premier euro soit engagé.

    Séparer la préparation de la dépense n'est pas cosmétique : la
    préparation est pure, déterministe et gratuite (compilation du contrat
    visuel, assemblage du prompt), alors que la production est un appel
    réseau payant. Tant que les deux étaient tressés dans une même boucle,
    on ne pouvait ni les paralléliser, ni reprendre plan par plan, ni
    montrer ce qui allait être envoyé sans le payer.
    """

    plan: PlanScript
    personnage: str
    prompt: str
    destination: Path
    contrat: ContratVisuel

    def en_image(self, cout: float, depuis_cache: bool) -> PlanImage:
        return PlanImage(
            numero=self.plan.numero, personnage=self.personnage,
            prompt=self.prompt, fichier=self.destination, cout=cout,
            depuis_cache=depuis_cache, contrat=self.contrat,
        )


def _preparer(plans: list[PlanScript], univers: Univers, dossier: Path, *,
              consignes: list[str] | None, marque_interdite: bool,
              vocabulaire) -> list[_Travail]:
    """Le travail de chaque plan, calculé d'avance et sans rien dépenser.

    Lève sur un personnage inconnu AVANT toute production : découvrir au
    plan 19 qu'un identifiant est absent de l'univers, après dix-huit
    images payées, est une façon coûteuse d'apprendre une faute de frappe.
    """
    travaux = []
    for plan in plans:
        perso = univers.personnage(plan.personnage)
        if perso is None:
            raise ErreurConfig(
                f"Plan {plan.numero} : personnage « {plan.personnage} » "
                f"absent de l'univers « {univers.nom} »."
            )
        risques_marque = (
            risque_prompt.mots_hors_vocabulaire(
                plan.action, plan.elements_obligatoires, vocabulaire)
            if marque_interdite else []
        )
        contrat = contrat_visuel.compiler(plan, perso, univers,
                                          risques_marque=risques_marque)
        for fait in decision_visuelle.verifier(contrat):
            log.info("Plan %d : décision visuelle — %s", plan.numero, fait)
        travaux.append(_Travail(
            plan=plan, personnage=perso.id,
            prompt=prompt_plan_depuis_contrat(contrat, univers,
                                              consignes=consignes),
            destination=dossier / f"plan_{plan.numero:03d}.jpg",
            contrat=contrat,
        ))
    return travaux


# Un plan d'images est une VAGUE : vingt-six appels réseau qui ne dépendent
# que des fiches de personnages, déjà produites. Les enchaîner un par un
# faisait attendre la somme des latences là où la somme n'a aucune raison
# d'être payée. Quatre à la fois est le plafond de l'ordonnanceur, choisi
# parce qu'au-delà les fournisseurs limitent — pas parce que 4 serait joli.
PARALLELISME_IMAGES = 4


async def fabriquer_dag(plans: list[PlanScript], univers: Univers, dossier: Path, *,
                        consignes: list[str] | None = None,
                        profil: str = "equilibre",
                        budget_max: float | None = None,
                        cache: bool = True,
                        job_id: str | None = None,
                        chemin_univers: Path | None = None,
                        parallelisme: int = PARALLELISME_IMAGES) -> Planche:
    """`fabriquer()`, mais les plans passent par l'ordonnanceur.

    Deux gains, et un seul est la vitesse.

    · **La reprise devient plan par plan.** `episode.py` journalisait les
      images comme UNE étape : un job interrompu au plan 20 sur 26
      repayait les vingt premières. Chaque plan est maintenant un nœud, et
      le journal — la même et seule autorité, `pdz/moteur/journal.py` —
      sait lequel est fait.
    · **Les appels se recouvrent**, jusqu'à `parallelisme`.

    Ce que cette fonction n'introduit PAS, délibérément : un second cache.
    `_produire()` a déjà le sien, keyé sur (prompt, graine, référence), et
    il est partagé entre épisodes. Les nœuds sont donc créés sans
    `cle_cache` : leur réutilisation passe par le journal pour la reprise,
    et par le cache image existant pour le reste. Empiler un troisième
    niveau reviendrait à cacher un cache.

    Le budget, honnêtement : le plafond est vérifié avant de LANCER chaque
    nœud, pas pendant. Avec `parallelisme` appels en vol, le dépassement
    maximal est de `parallelisme - 1` images — quelques centimes, contre
    des minutes d'attente gagnées. La version séquentielle reste
    disponible pour qui veut la garantie stricte.
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

    marque_interdite = risque_prompt.marque_est_interdite(univers.interdits)
    vocabulaire = frozenset()
    if marque_interdite:
        noms_connus = [x for p in univers.personnages for x in (p.id, p.nom, p.espece)] \
                     + [x for d in univers.decors for x in (d.id, d.nom)]
        vocabulaire = risque_prompt.vocabulaire_connu(noms_connus)

    travaux = _preparer(plans, univers, dossier, consignes=consignes,
                        marque_interdite=marque_interdite,
                        vocabulaire=vocabulaire)
    par_noeud = {f"image_{t.plan.numero:03d}": t for t in travaux}
    # Un dictionnaire indexé par numéro de plan écraserait silencieusement
    # un doublon, et la planche reviendrait plus courte que le storyboard.
    # La boucle séquentielle ne pouvait pas faire ça — elle empilait une
    # entrée par itération. L'erreur ne réapparaîtrait qu'au montage, sur un
    # `zip(..., strict=True)` très loin d'ici, avec un message qui ne
    # nommerait pas la cause.
    if len(par_noeud) != len(travaux):
        vus, doublons = set(), []
        for t in travaux:
            (doublons.append(t.plan.numero) if t.plan.numero in vus
             else vus.add(t.plan.numero))
        raise ErreurConfig(
            f"Numéros de plan en double dans le storyboard : {sorted(set(doublons))}. "
            "Chaque plan doit avoir un numéro unique — sinon une image en "
            "écrase une autre."
        )

    # Un compteur partagé plutôt qu'une somme finale : c'est lui qui permet
    # d'ARRÊTER de dépenser, ce qu'un total calculé après coup ne peut plus
    # faire. asyncio est mono-thread, donc le lire et l'écrire hors de tout
    # `await` suffit — aucun verrou n'est nécessaire ici, et en ajouter un
    # laisserait croire à une protection contre des threads qui n'existent pas.
    depense = 0.0

    async def produire_une_image(noeud, _entrees):
        nonlocal depense
        travail = par_noeud[noeud.noeud_id]
        if depense >= plafond:
            raise ErreurBudget(
                f"Plafond de {plafond:.2f} € atteint. Relancer la commande "
                "reprendra ici — les plans déjà produits sont journalisés "
                "et ne seront pas repayés."
            )
        reste_pct = max(0.0, (plafond - depense) / max(1e-6, plafond) * 100)
        # `to_thread` : `_produire` est un appel réseau bloquant. Le laisser
        # sur la boucle événementielle sérialiserait tout et rendrait le DAG
        # décoratif.
        cout, du_cache = await asyncio.to_thread(
            _produire, travail.prompt, travail.destination, univers=univers,
            reference=planche.fiches.get(travail.personnage), profil=profil,
            budget_restant_pct=reste_pct, cache=cache, job_id=job_id,
        )
        depense += cout
        return {"fichier": str(travail.destination), "cout_eur": cout,
                "depuis_cache": du_cache, "prompt": travail.prompt}

    plan_execution = ExecutionPlan(
        shot_id=job_id or "",
        noeuds=tuple(
            NoeudExecution(noeud_id=noeud_id, operation="image",
                           cout_estime_eur=plafond / max(1, len(travaux)))
            for noeud_id in par_noeud
        ),
    )
    resultat = await executer(
        plan_execution, {"image": produire_une_image},
        job_id=job_id or "sans-job", parallelisme_max=parallelisme,
    )

    # Un échec d'image n'est PAS rattrapable ici : le montage exige une image
    # par plan (`zip(..., strict=True)`). L'ordonnanceur laisse les branches
    # indépendantes finir — c'est ce qu'on veut, le travail déjà payé est
    # gardé — mais l'appelant doit apprendre l'échec, comme le faisait la
    # version séquentielle en laissant remonter l'exception.
    if resultat.echoues:
        premier = resultat.plan.par_id(resultat.echoues[0])
        detail = (premier.erreur if premier else "") or "cause inconnue"
        message = (f"{len(resultat.echoues)} plan(s) sans image sur "
                   f"{len(travaux)} — premier échec : {detail}")
        # Le budget garde son type d'erreur : `episode.py` et la CLI le
        # distinguent d'une panne, et l'aplatir en ErreurConfig ferait
        # passer « tu as atteint ton plafond » pour « ta configuration est
        # cassée » — deux situations qui n'appellent pas la même réaction.
        raise (ErreurBudget(message) if "Plafond" in detail
               else ErreurConfig(message))

    # L'ordre des plans est celui du storyboard, jamais celui d'arrivée des
    # réponses : le montage zippe plans et images position par position, et
    # une planche triée par latence produirait un épisode dont les images
    # sont mélangées — sans qu'aucun test de comptage ne le remarque.
    for noeud_id, travail in par_noeud.items():
        sortie = resultat.sorties[noeud_id]
        planche.plans.append(travail.en_image(
            float(sortie.get("cout_eur", 0.0) or 0.0),
            bool(sortie.get("depuis_cache", False)),
        ))
    # `resultat.cout_eur` et non la somme des plans : ce que l'appelant doit
    # connaître, c'est ce que CETTE exécution a dépensé, parce que c'est ça
    # qui se compare au plafond. Un plan repris du journal porte son coût
    # d'origine — utile comme provenance sur `PlanImage.cout`, faux comme
    # dépense du jour. Les additionner ferait recompter, à chaque reprise,
    # de l'argent déjà dépensé la fois d'avant, et rapprocherait le plafond
    # à chaque relance jusqu'à interdire une reprise qui ne coûte rien.
    planche.cout = resultat.cout_eur
    planche.images_evitees = (
        len(resultat.reutilises)
        + sum(1 for p in planche.plans if p.depuis_cache)
    )

    log.info("Images (DAG) : %s", planche.resume())
    return planche


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

    # Vocabulaire propre à l'univers, construit une fois — pas un import
    # depuis `episode.py` : ce vocabulaire ne coûte rien à reconstruire
    # (aucun appel IA), et le texte du plan a pu changer depuis le routage
    # RealismWriter (voir episode.py) — le recalculer ici garantit que le
    # contrat journalisé reflète le prompt RÉELLEMENT envoyé, pas un signal
    # devenu obsolète après correction.
    marque_interdite = risque_prompt.marque_est_interdite(univers.interdits)
    vocabulaire = frozenset()
    if marque_interdite:
        noms_connus = [x for p in univers.personnages for x in (p.id, p.nom, p.espece)] \
                     + [x for d in univers.decors for x in (d.id, d.nom)]
        vocabulaire = risque_prompt.vocabulaire_connu(noms_connus)

    for travail in _preparer(plans, univers, dossier, consignes=consignes,
                             marque_interdite=marque_interdite,
                             vocabulaire=vocabulaire):
        if planche.cout >= plafond:
            raise ErreurBudget(
                f"Plafond de {plafond:.2f} € atteint après {len(planche.plans)} "
                "plans. Relancer la commande reprendra ici — les plans déjà "
                "produits sont en cache et ne seront pas repayés."
            )

        reste_pct = max(0.0, (plafond - planche.cout) / max(1e-6, plafond) * 100)
        cout, du_cache = _produire(
            travail.prompt, travail.destination, univers=univers,
            reference=planche.fiches.get(travail.personnage), profil=profil,
            budget_restant_pct=reste_pct, cache=cache, job_id=job_id,
        )
        planche.plans.append(travail.en_image(cout, du_cache))
        planche.cout += cout
        planche.images_evitees += int(du_cache)

    log.info("Images : %s", planche.resume())
    return planche
