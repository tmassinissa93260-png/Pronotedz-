"""La chaîne complète : d'une situation à un fichier .mp4.

Sept étapes, dans cet ordre, et l'ordre a des raisons — l'écriture elle-même
se décompose en trois passes séparées, une IA par responsabilité plutôt qu'un
seul appel qui fait tout à la fois :

    1. brief         situation             → structure narrative (beats)
    1b. script       beats + univers       → dialogue + action minimale
    2. voix          répliques             → audio + timings RÉELS
    3. découpage     répliques + durées    → plans
    3b. prompts      plans déjà découpés   → prompt d'image par plan
    3c. réalisme     prompts déjà écrits   → prompts corrigés (rien d'illisible)
    4. images        plans + univers       → une image par plan
    5. animation     plans notés + budget  → clips pour les plans qui comptent
    6. sous-titres   timings réels         → karaoké calé au mot
    7. montage       tout ce qui précède   → l'épisode

Les prompts d'image passent **après** le découpage, pas avec le dialogue :
un plan de réaction (« celui qui écoute ») n'existe qu'une fois le découpage
fait, et doit recevoir, lui aussi, un prompt écrit pour lui — pas une action
générique recopiée à chaque réplique qui a une réaction.

La passe « réalisme » (3c) ne génère jamais d'image : elle relit chaque
prompt en texte seul et remplace ce qu'un modèle d'image rate toujours
(texte lisible, logo, visage interdit par l'univers) par un équivalent
qu'il sait rendre. Corriger ça en amont, gratuitement en tentatives Groq,
coûte moins qu'un agent de vision qui vérifierait l'image APRÈS coup — ce
dernier double la consommation (image ratée, vérification, regénération)
au lieu de l'éviter. Elle ne tourne même plus sur CHAQUE plan : un filtre
déterministe (`pdz.production.risque_prompt`, zéro appel IA) décide d'abord
lesquels le méritent vraiment — la plupart des plans n'ont rien à corriger.

Le découpage (3) profite du même principe côté durée : le point de coupe
parlant/réaction suit une vraie pause de la voix (`storyboard.point_de_coupe`)
quand on peut la retrouver dans les timings mesurés, au lieu d'un pourcentage
fixe qui coupe parfois en plein milieu d'un mot.

La voix passe **avant** les images, ce qui surprend au premier abord. C'est le
choix central du module : la durée d'un plan doit venir de la parole réellement
prononcée, pas d'une estimation. Dans l'autre sens, on fabrique des images pour
des durées supposées, puis on découvre que la réplique dure 1,3 s de plus, et
tout glisse.

Chaque étape est enregistrée en base. Relancer la même commande après un
plantage, une coupure ou trois jours reprend là où ça s'était arrêté, sans
repayer ce qui est déjà produit — c'est le même mécanisme que le moteur
(docs/06-solidite.md), appliqué ici à des fichiers plutôt qu'à du JSON.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pdz import db
from pdz.agents.ecriture.brief import BriefWriter
from pdz.agents.ecriture.plans import ShotPromptWriter
from pdz.agents.ecriture.realisme import RealismWriter
from pdz.agents.ecriture.script import ScriptWriter
from pdz.analyse.adn import Adn
from pdz.analyse.sonde import sonder
from pdz.config import config
from pdz.moteur.erreurs import ErreurConfig, ErreurPdz, ErreurValidation
from pdz.moteur.pipeline import Contexte, executer_avec_relance
from pdz.production import (
    animation, coherence_duree, continuite, images, qa_images, risque_prompt,
    storyboard, voix,
)
from pdz.production.storyboard import PlanScript
from pdz.univers import Univers
from pdz.video import soustitres
from pdz.video.montage import Montage, Mouvement, Plan, preparer_image

log = logging.getLogger(__name__)


@dataclass
class Episode:
    job_id: str
    titre: str
    video: Path
    duree_s: float
    cout: float
    script: dict = field(default_factory=dict)
    plans: list[PlanScript] = field(default_factory=list)
    etapes_reprises: list[str] = field(default_factory=list)
    plans_animes: int = 0

    def resume(self) -> str:
        repris = (f" · {len(self.etapes_reprises)} étape(s) reprises sans repayer"
                  if self.etapes_reprises else "")
        # L'animation se lit dans le résumé, pas seulement dans les journaux :
        # « 0 animé » est une information, et son absence a longtemps caché un
        # identifiant de modèle périmé.
        anim = (f" · {self.plans_animes} plan(s) animé(s)" if self.plans_animes
                else " · aucune animation (images fixes)")
        return (f"« {self.titre} » · {self.duree_s:.1f} s · "
                f"{len(self.plans)} plans{anim} · {self.cout:.3f} €{repris}\n"
                f"   {self.video}")


# ── Reprise : une étape faite est une étape qu'on ne refait pas ──────────

def _fait(job_id: str, cle: str) -> dict | None:
    """Relit une étape terminée. `None` si elle reste à faire.

    Les fichiers sont revérifiés : une étape marquée terminée dont les
    fichiers ont été supprimés doit être refaite, sinon le montage échoue
    trente secondes plus tard sur une erreur incompréhensible.
    """
    with db.connexion() as conn:
        ligne = conn.execute(
            "SELECT resultat FROM etapes WHERE job_id = ? AND cle = ? "
            "AND statut = 'termine'", (job_id, cle),
        ).fetchone()

    if ligne is None:
        return None

    resultat = db.charger(ligne["resultat"], None)
    if resultat is None:
        return None

    for chemin in _fichiers_cites(resultat):
        if not Path(chemin).exists():
            log.info("Étape « %s » à refaire : %s a disparu", cle, chemin)
            return None
    return resultat


def _fichiers_cites(valeur: Any) -> list[str]:
    """Tous les chemins de fichiers mentionnés dans un résultat d'étape."""
    trouves: list[str] = []
    if isinstance(valeur, str):
        if "/" in valeur and Path(valeur).suffix in (
            ".mp3", ".mp4", ".jpg", ".png", ".ass", ".wav"
        ):
            trouves.append(valeur)
    elif isinstance(valeur, dict):
        for v in valeur.values():
            trouves += _fichiers_cites(v)
    elif isinstance(valeur, list):
        for v in valeur:
            trouves += _fichiers_cites(v)
    return trouves


def _noter(job_id: str, cle: str, agent: str, resultat: dict,
           cout: float, duree_ms: int) -> None:
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO etapes (id, job_id, cle, agent, statut, resultat, cout,"
            " duree_ms, cree_le, fini_le) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(job_id, cle) DO UPDATE SET "
            "  statut = 'termine', resultat = excluded.resultat, "
            "  cout = excluded.cout, duree_ms = excluded.duree_ms, "
            "  fini_le = excluded.fini_le, tentative = etapes.tentative + 1",
            (db.nouvel_id("etp"), job_id, cle, agent, "termine",
             db.vider(resultat), cout, duree_ms, db.maintenant(), db.maintenant()),
        )
        conn.execute(
            "UPDATE jobs SET cout_total = cout_total + ?, maj_le = ? WHERE id = ?",
            (cout, db.maintenant(), job_id),
        )


def creer_job(univers: Univers, situation: str, *, profil: str,
              budget_max: float | None = None) -> str:
    job_id = db.nouvel_id("job")
    plafond = budget_max if budget_max is not None else config().budget_max_par_video_eur
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO jobs (id, type, statut, entree, profil, budget_max,"
            " cree_le, maj_le) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, "video_depuis_idee", "en_cours",
             json.dumps({"univers": univers.id, "situation": situation},
                        ensure_ascii=False),
             profil, plafond, db.maintenant(), db.maintenant()),
        )
    return job_id


# ── La chaîne ────────────────────────────────────────────────────────────

async def produire(univers: Univers, situation: str, sortie: Path, *,
                   duree_s: float | None = None,
                   profil: str = "equilibre",
                   adn: Adn | None = None,
                   beats: list[dict] | None = None,
                   resume_precedent: str = "",
                   budget_max: float | None = None,
                   job_id: str | None = None,
                   musique: Path | None = None,
                   avec_animation: bool = True,
                   chemin_univers: Path | None = None,
                   style_soustitres: soustitres.StyleSousTitres | None = None,
                   ) -> Episode:
    """Fabrique un épisode complet. Reprend une production interrompue."""
    cfg = config()
    plafond = budget_max if budget_max is not None else cfg.budget_max_par_video_eur
    job_id = job_id or creer_job(univers, situation, profil=profil,
                                 budget_max=plafond)

    travail = cfg.dossier_travail / job_id
    travail.mkdir(parents=True, exist_ok=True)
    repris: list[str] = []
    cout_total = 0.0

    # ── 1a. Brief ────────────────────────────────────────────────────────
    # La structure narrative — et la stratégie créative qui la justifie —
    # avant tout dialogue : sans elles, ScriptWriter invente sa propre
    # mécanique de rétention à chaque appel, sans garde-fou sur le nombre de
    # temps forts ni leur répartition dans le temps, et redécide
    # implicitement sa propre stratégie réplique par réplique.
    strategie = None
    if beats is None:
        fait_brief = _fait(job_id, "brief")
        if fait_brief is None:
            debut = time.perf_counter()
            ctx = Contexte(job_id=job_id, etape_cle="brief", profil=profil,
                           budget_restant=plafond - cout_total)
            brief = await executer_avec_relance(BriefWriter(),
                {"univers": univers, "situation": situation, "duree_s": duree_s},
                ctx,
            )
            _noter(job_id, "brief", "brief", brief, ctx.cout_engage,
                   int((time.perf_counter() - debut) * 1000))
            cout_total += ctx.cout_engage
        else:
            repris.append("brief")
            brief = fait_brief
        beats = brief["beats"]
        strategie = brief.get("strategie")

    # ── 1b. Script ───────────────────────────────────────────────────────
    script = _fait(job_id, "script")
    if script is None:
        debut = time.perf_counter()
        ctx = Contexte(job_id=job_id, etape_cle="script", profil=profil,
                       budget_restant=plafond - cout_total)
        script = await executer_avec_relance(ScriptWriter(),
            {"univers": univers, "situation": situation, "duree_s": duree_s,
             "adn": adn, "beats": beats, "strategie": strategie,
             "resume_precedent": resume_precedent},
            ctx,
        )
        _noter(job_id, "script", "script", script, ctx.cout_engage,
               int((time.perf_counter() - debut) * 1000))
        cout_total += ctx.cout_engage
    else:
        repris.append("script")

    repliques = script["repliques"]
    log.info("Script « %s » : %d répliques", script.get("titre", "?"), len(repliques))

    # Un plan sans décor précisé hérite du dernier décor explicite, plutôt
    # que de retomber plus loin sur un décor générique sans rapport avec la
    # scène en cours — voir pdz/production/continuite.py. Seulement pour les
    # univers à personnages récurrents : en narration, `decor` reste
    # délibérément épars, hériter n'y aurait aucun sens.
    if univers.anime:
        repliques = continuite.porter_le_decor(repliques)

    # ── 2. Voix ──────────────────────────────────────────────────────────
    # Avant les images : c'est la durée réelle de chaque réplique qui fixera
    # la durée de chaque plan.
    fait_voix = _fait(job_id, "voix")
    piste = travail / "voix.m4a"
    if fait_voix is None:
        debut = time.perf_counter()
        bande = voix.dire(repliques, univers, piste, job_id=job_id)
        _noter(job_id, "voix", "voix", {
            "fichier": str(bande.fichier),
            "duree_ms": bande.duree_ms,
            # Les durées COUVRANTES, silences compris : c'est ce qui garantit
            # que l'image dure aussi longtemps que le son.
            "durees_couvrantes_s": bande.durees_couvrantes_s,
            "mots": [[m.texte, m.debut_ms, m.fin_ms] for m in bande.mots],
            # Les frontières entre répliques : sans elles, un sous-titre peut
            # mêler les paroles de deux personnages.
            "debuts_repliques": sorted(bande.debuts_de_replique),
        }, 0.0, int((time.perf_counter() - debut) * 1000))
        durees = bande.durees_couvrantes_s
        mots = bande.mots
        debuts_repliques = bande.debuts_de_replique
    else:
        repris.append("voix")
        piste = Path(fait_voix["fichier"])
        durees = fait_voix["durees_couvrantes_s"]
        mots = [soustitres.Mot(t, d, f) for t, d, f in fait_voix["mots"]]
        # `.get` : une production notée avant l'ajout de ce champ se reprend
        # sans lui plutôt que d'échouer.
        debuts_repliques = frozenset(fait_voix.get("debuts_repliques") or [])

    # Un job repris peut relire des durées mises en cache pendant qu'un
    # fichier voix plus récent (donc plus ou moins long) a été régénéré à
    # côté — voir pdz/production/coherence_duree.py. Détecté ici, avant de
    # payer images et animation pour la mauvaise durée.
    mesure_s = voix.duree_ms(piste) / 1000
    if (msg := coherence_duree.message_si_incoherent(
        sum(durees), mesure_s, contexte="Voix",
    )):
        raise ErreurValidation(
            f"{msg} Le fichier voix et les timings utilisés pour découper "
            f"l'épisode ne sont pas d'accord — relance sans --reprendre."
        )

    # ── 3. Découpage ─────────────────────────────────────────────────────
    # Le point de coupe parlant/réaction suit une vraie pause de la voix
    # quand on peut la retrouver, plutôt qu'un pourcentage fixe — voir
    # storyboard.point_de_coupe(). `mots` porte déjà cette information,
    # qu'elle vienne d'une synthèse fraîche ou d'une reprise.
    mots_par_replique = storyboard.grouper_mots_par_replique(mots, debuts_repliques)
    plans = storyboard.decouper(repliques, durees, univers,
                                mots_par_replique=mots_par_replique)
    log.info("Découpage : %s", storyboard.resume(plans))

    # ── 3b. Prompts d'image ─────────────────────────────────────────────
    # Séparé du dialogue exprès (voir pdz/agents/ecriture/plans.py), et
    # APRÈS le découpage, pas avant : un plan de réaction (« celui qui
    # écoute ») n'existe qu'une fois le découpage fait — l'écrire par
    # réplique aurait laissé ces plans-là sur une action générique
    # (« il/elle réagit, écoute ») jamais vue par ce modèle. Un modèle qui
    # ne s'occupe QUE du cadrage, une fois le texte ET le montage figés,
    # écrit un prompt plus riche que l'action notée en même temps que le
    # dialogue — et cette fois pour CHAQUE plan, pas seulement pour celui
    # qui parle.
    fait_prompts = _fait(job_id, "shot_prompts")
    if fait_prompts is None:
        debut = time.perf_counter()
        ctx = Contexte(job_id=job_id, etape_cle="shot_prompts", profil=profil,
                       budget_restant=plafond - cout_total)
        prompts = await executer_avec_relance(ShotPromptWriter(),
            {"univers": univers, "plans": plans, "repliques": repliques}, ctx,
        )
        _noter(job_id, "shot_prompts", "shot_prompts", prompts, ctx.cout_engage,
               int((time.perf_counter() - debut) * 1000))
        cout_total += ctx.cout_engage
    else:
        repris.append("shot_prompts")
        prompts = fait_prompts
    plans = ShotPromptWriter().fusionner(plans, prompts)

    # ── 3c. Réalisme ─────────────────────────────────────────────────────
    # Texte seul, aucun appel image : corrige ce qu'un modèle de génération
    # d'image rate systématiquement (texte lisible, logo, visage interdit)
    # AVANT de payer une image pour ça — voir pdz/agents/ecriture/realisme.py.
    # Filtré par un risque déterministe (pdz/production/risque_prompt.py) :
    # appeler RealismWriter sur CHAQUE plan, à chaque fois, coûtait un appel
    # Groq de plus par plan même quand rien dans le prompt ne l'exigeait —
    # exactement ce qui a vidé le quota Groq en pleine production.
    visage_interdit = risque_prompt.visage_est_interdit(univers.style.consignes_image)
    a_verifier = [
        p for p in plans
        if risque_prompt.raisons_de_correction(p.action, visage_interdit=visage_interdit)
    ]
    # Capturé AVANT la fusion ci-dessous, qui reconstruit `plans` : une
    # réécriture de prompt par RealismWriter est un second endroit où un
    # élément obligatoire peut disparaître — voir pdz/production/qa_images.py.
    numeros_realisme = {p.numero for p in a_verifier}
    if not a_verifier:
        log.info("Réalisme : aucun plan à risque, étape sautée (0 appel IA)")
    else:
        fait_realisme = _fait(job_id, "realisme")
        if fait_realisme is None:
            debut = time.perf_counter()
            ctx = Contexte(job_id=job_id, etape_cle="realisme", profil=profil,
                           budget_restant=plafond - cout_total)
            corrections = await executer_avec_relance(RealismWriter(),
                {"univers": univers, "plans": a_verifier}, ctx,
            )
            _noter(job_id, "realisme", "realisme", corrections, ctx.cout_engage,
                   int((time.perf_counter() - debut) * 1000))
            cout_total += ctx.cout_engage
        else:
            repris.append("realisme")
            corrections = fait_realisme
        plans = RealismWriter().fusionner(plans, corrections)

    # ── 4. Images ────────────────────────────────────────────────────────
    fait_images = _fait(job_id, "images")
    if fait_images is None:
        debut = time.perf_counter()
        planche = images.fabriquer(
            plans, univers, travail / "images",
            consignes=(adn.consignes_image if adn else None),
            profil=profil, budget_max=plafond - cout_total,
            job_id=job_id, chemin_univers=chemin_univers,
        )
        _noter(job_id, "images", "directeur_image",
               {"fichiers": [str(f) for f in planche.fichiers]},
               planche.cout, int((time.perf_counter() - debut) * 1000))
        cout_total += planche.cout
        fichiers = planche.fichiers
    else:
        repris.append("images")
        fichiers = [Path(f) for f in fait_images["fichiers"]]

    if len(fichiers) != len(plans):
        raise ErreurPdz(
            f"{len(plans)} plans mais {len(fichiers)} images reprises. "
            f"Le script a changé depuis : relance avec un nouveau job "
            f"(`pdz episode ...` sans --reprendre)."
        )

    # ── 4b. Vérification visuelle ciblée ────────────────────────────────
    # Vision, donc jamais gratuite — c'est pour ça qu'elle ne tourne QUE sur
    # les plans qui ont déjà montré un signe de dérive côté texte (voir
    # pdz/production/qa_images.py), jamais sur tous les plans, et jamais
    # avant que l'image existe réellement.
    numeros_qa = qa_images.plans_a_verifier(plans, numeros_realisme)
    fait_qa = _fait(job_id, "qa_images")
    if not numeros_qa:
        log.info("QA image : aucun plan à risque, étape sautée (0 appel IA)")
    elif fait_qa is None:
        debut = time.perf_counter()
        repliques_par_numero = {r["numero"]: r["replique"] for r in repliques}
        verifications, fichiers, cout_qa = await qa_images.verifier(
            plans, fichiers, numeros_qa, univers, dossier=travail / "images",
            profil=profil, budget_restant=plafond - cout_total, job_id=job_id,
            chemin_univers=chemin_univers, repliques_par_numero=repliques_par_numero,
        )
        _noter(job_id, "qa_images", "qa_image",
               {"verifications": verifications, "fichiers": [str(f) for f in fichiers]},
               cout_qa, int((time.perf_counter() - debut) * 1000))
        cout_total += cout_qa
        besoin_revue = [v["numero"] for v in verifications if v["statut"] == "NEEDS_REVIEW"]
        if besoin_revue:
            log.error("QA image : plan(s) %s toujours en écart après regénération "
                     "— gardés tel quels, à revoir.", besoin_revue)
    else:
        repris.append("qa_images")
        fichiers = [Path(f) for f in fait_qa["fichiers"]]

    # ── 5. Animation ─────────────────────────────────────────────────────
    fait_anim = _fait(job_id, "animation")
    if fait_anim is None and avec_animation:
        debut = time.perf_counter()
        animes = animation.animer(
            [p.en_dict() for p in plans], fichiers, univers, travail / "animation",
            budget_restant=max(0.0, plafond - cout_total), profil=profil,
            job_id=job_id,
        )
        cout_anim = sum(a.cout for a in animes)
        _noter(job_id, "animation", "animation", {
            "plans": [{"index": a.index, "fichier": str(a.fichier),
                       "anime": a.anime, "methode": a.methode} for a in animes],
        }, cout_anim, int((time.perf_counter() - debut) * 1000))
        cout_total += cout_anim
    elif fait_anim is not None:
        repris.append("animation")
        animes = [
            animation.PlanAnime(a["index"], Path(a["fichier"]), a["anime"],
                                a["methode"])
            for a in fait_anim["plans"]
        ]
    else:
        animes = [animation.PlanAnime(i, f, False, "camera")
                  for i, f in enumerate(fichiers)]

    # ── 6. Sous-titres ───────────────────────────────────────────────────
    fichier_ass = travail / "soustitres.ass"
    fichier_ass.write_text(
        soustitres.generer_ass(mots, largeur=cfg.largeur, hauteur=cfg.hauteur,
                               style=style_soustitres,
                               debuts_de_replique=debuts_repliques),
        encoding="utf-8",
    )

    # ── 7. Montage ───────────────────────────────────────────────────────
    debut = time.perf_counter()
    montage = _preparer_montage(plans, animes, travail, piste, fichier_ass,
                                musique, cfg)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    montage.rendre(sortie)
    log.info("Montage rendu en %.1f s", time.perf_counter() - debut)

    # Dernier filet, après coup : un clip animé plus court que prévu ou un
    # souci ffmpeg peut raccourcir la vidéo sans que rien d'autre ne le
    # voie. L'épisode est déjà payé — on ne le jette pas pour ça — mais un
    # écart doit être IMPOSSIBLE à manquer dans les journaux (voir
    # pdz/production/coherence_duree.py, et le run qui a produit 28 s de
    # vidéo pour 43 s de voix sans une seule erreur).
    if (msg := coherence_duree.message_si_incoherent(
        sum(p.duree_s for p in plans), sonder(sortie).duree_s, contexte="Montage",
    )):
        log.error("%s L'épisode livré est probablement tronqué.", msg)

    with db.connexion() as conn:
        conn.execute("UPDATE jobs SET statut = 'termine', maj_le = ? WHERE id = ?",
                     (db.maintenant(), job_id))

    return Episode(
        job_id=job_id, titre=script.get("titre", "sans titre"), video=sortie,
        duree_s=sum(p.duree_s for p in plans), cout=cout_total,
        script=script, plans=plans, etapes_reprises=repris,
        plans_animes=sum(1 for a in animes if a.anime),
    )


def _preparer_montage(plans: list[PlanScript], animes: list[animation.PlanAnime],
                      travail: Path, piste: Path, sous_titres: Path,
                      musique: Path | None, cfg) -> Montage:
    """Assemble les plans pour le montage final.

    Les images fixes sont agrandies une fois avec Pillow pour donner à la
    fenêtre de recadrage la place de bouger — c'est ce qui permet d'éviter
    `zoompan` côté ffmpeg, mesuré 25 à 40 fois plus lent.
    """
    prets = travail / "prets"
    prets.mkdir(parents=True, exist_ok=True)

    montes: list[Plan] = []
    for plan, anime in zip(plans, animes, strict=True):
        if anime.anime:
            montes.append(Plan(image=anime.fichier, duree_s=plan.duree_s,
                               anime=True))
            continue
        prete = preparer_image(anime.fichier, prets / f"{plan.numero:03d}.jpg",
                               largeur=cfg.largeur, hauteur=cfg.hauteur)
        montes.append(Plan(image=prete, duree_s=plan.duree_s,
                           mouvement=Mouvement.alterne(plan.numero)))

    if musique is not None and not Path(musique).exists():
        raise ErreurConfig(f"Musique introuvable : {musique}")

    return Montage(
        plans=montes, voix=piste, musique=musique, sous_titres=sous_titres,
        LARGEUR=cfg.largeur, HAUTEUR=cfg.hauteur, FPS=cfg.fps,
    )
