"""Confronte ce qui était voulu à ce qui a été mesuré.

── Pourquoi un `Attendu` explicite ──────────────────────────────────────

Le diagnostic ne relit pas le `MotionProgram` : il vivrait alors dans la
couche de décision, et le sens de la dépendance s'inverserait. On lui passe
donc l'attendu, réduit à ce qui est VÉRIFIABLE — trois questions, pas trente :

    le sujet devait-il bouger ?   la caméra devait-elle bouger ?
    combien de temps devait durer le plan ?

Tout le reste (identité, couleur, géométrie) attend une sonde qui sache le
mesurer. Le déclarer sans pouvoir l'observer produirait des diagnostics
`INCONNU` en série — exact, mais inutile.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdz.contracts.communs import Severite, Verdict
from pdz.contracts.diagnosis import Ecart, FailureDiagnosis, ModeEchec
from pdz.contracts.observation import Axe, ObservationReport


@dataclass(frozen=True)
class Attendu:
    """Ce que le plan devait produire — seulement ce qui est vérifiable."""

    shot_id: str = ""
    # `True` quand un mouvement de sujet a réellement été DÉCIDÉ. Un plan
    # sans mouvement décidé n'échoue pas s'il ne bouge pas : c'est ce qui
    # était demandé.
    sujet_doit_bouger: bool = False
    camera_doit_bouger: bool = False
    duree_s: float = 0.0
    # Ce que le contrat perceptuel interdit de confondre. C'est ce qui
    # transforme « mouvement faible » en `CAMERA_DOMINANT`.
    confusions_interdites: tuple[str, ...] = ()
    # 0..1 — gradue la sévérité : rater le plan qui porte l'épisode n'a pas
    # la même conséquence que rater un plan de transition.
    importance: float = 0.0


def ecarts(attendu: Attendu, rapport: ObservationReport) -> tuple[Ecart, ...]:
    """Les différences mesurables entre le voulu et l'observé.

    Ne conclut rien : ce sont les PREUVES sur lesquelles `diagnostiquer()`
    s'appuiera. Les séparer permet de relire un diagnostic contesté sans
    refaire la mesure.
    """
    trouves: list[Ecart] = []

    if attendu.sujet_doit_bouger and rapport.verdict_axe(Axe.MOUVEMENT) is Verdict.ECHOUE:
        mesure = next((m for m in rapport.par_axe(Axe.MOUVEMENT)
                       if m.verdict is Verdict.ECHOUE), None)
        trouves.append(Ecart(
            dimension="mouvement_sujet", attendu="mouvement perceptible",
            observe=mesure.valeur if mesure else "aucun mouvement mesuré",
        ))

    for axe, attendu_par_defaut in ((Axe.TEMPOREL, ""), (Axe.TECHNIQUE, "fichier lisible")):
        for mesure in rapport.par_axe(axe):
            if mesure.verdict is Verdict.ECHOUE:
                trouves.append(Ecart(
                    dimension=mesure.nom,
                    attendu=mesure.attendu or attendu_par_defaut,
                    observe=mesure.valeur or mesure.detail,
                ))

    return tuple(trouves)


def _severite(importance: float, mode: ModeEchec) -> Severite:
    """Rater le plan qui porte l'épisode n'a pas la même conséquence que
    rater un plan de transition."""
    if mode is ModeEchec.INCONNU:
        return Severite.INFO
    if importance >= 0.7:
        return Severite.CRITIQUE
    return Severite.MAJEURE if importance >= 0.3 else Severite.MINEURE


def diagnostiquer(attendu: Attendu, rapport: ObservationReport) -> FailureDiagnosis | None:
    """L'hypothèse de cause la plus probable, ou `None` si rien ne cloche.

    `None` est un RÉSULTAT, pas une absence : il dit « l'observation ne
    contredit pas l'intention ». Distinct d'un `INCONNU`, qui dirait « on n'a
    pas pu savoir ».

    L'ordre des règles compte — la première qui s'applique gagne, et elles
    vont du plus SPÉCIFIQUE au plus général. Un `CAMERA_DOMINANT` doit être
    détecté avant un `MOUVEMENT_FAIBLE` générique : les deux voient un
    mouvement de sujet insuffisant, mais un seul dit quoi corriger.
    """
    preuves = ecarts(attendu, rapport)

    # ── 1. Le fichier lui-même ──────────────────────────────────────────
    if rapport.verdict_axe(Axe.TECHNIQUE) is Verdict.ECHOUE:
        return _diagnostic(attendu, ModeEchec.DUREE_INCORRECTE, preuves,
                           confiance=0.95, rapport=rapport,
                           explication="le fichier rendu n'est pas exploitable",
                           reparations=("STRATEGY_FIX", "MODEL_FIX"))

    # ── 2. Le mouvement ─────────────────────────────────────────────────
    mouvement = rapport.verdict_axe(Axe.MOUVEMENT)

    if attendu.sujet_doit_bouger and mouvement is Verdict.ECHOUE:
        # `CAMERA_DOMINANT` d'abord, MAIS seulement si la caméra avait le
        # droit de bouger.
        #
        # Une première version se contentait de la confusion déclarée. C'était
        # faux, et un test l'a montré : sur un plan à caméra VERROUILLÉE, ce
        # diagnostic menait à « verrouiller la caméra », c'est-à-dire à ne
        # rien changer — une réparation sans effet est une relance déguisée.
        #
        # Le raisonnement le confirme : si la caméra avait bougé, la sonde
        # aurait MESURÉ du mouvement. Un clip statique dont la caméra était
        # verrouillée n'a pas « une caméra dominante », il n'a rien du tout.
        if (attendu.camera_doit_bouger
                and "camera_only_motion" in attendu.confusions_interdites):
            return _diagnostic(
                attendu, ModeEchec.CAMERA_DOMINANTE, preuves,
                # Plus basse que les autres, volontairement : sans sonde qui
                # SÉPARE le mouvement de caméra de celui du sujet, c'est une
                # hypothèse fondée sur l'intention, pas une mesure. Le dire
                # est plus utile que d'affirmer.
                confiance=0.6, rapport=rapport,
                explication="le sujet devait bouger et ne bouge pas ; le plan "
                            "déclarait vouloir éviter qu'on prenne un mouvement "
                            "de caméra pour celui du sujet",
                reparations=("CAMERA_FIX", "MOTION_FIX", "STRATEGY_FIX"),
            )
        if not attendu.camera_doit_bouger:
            # Rien ne devait bouger sauf le sujet, et rien ne bouge : le
            # rendu est simplement statique.
            return _diagnostic(
                attendu, ModeEchec.RENDU_STATIQUE, preuves, confiance=0.9,
                rapport=rapport,
                explication="aucun mouvement mesuré alors que le sujet devait agir",
                reparations=("MOTION_FIX", "PROMPT_FIX", "STRATEGY_FIX"),
            )
        return _diagnostic(
            attendu, ModeEchec.MOUVEMENT_SUJET_ABSENT, preuves, confiance=0.8,
            rapport=rapport,
            explication="le mouvement de sujet demandé n'est pas perceptible",
            reparations=("MOTION_FIX", "STRATEGY_FIX"),
        )

    if attendu.sujet_doit_bouger and mouvement is Verdict.INCERTAIN:
        # Ni confirmé, ni infirmé. Ce n'est pas un échec du plan, c'est un
        # échec de la MESURE — et le traiter comme un échec du plan ferait
        # dépenser pour réparer quelque chose qui va peut-être très bien.
        return _diagnostic(
            attendu, ModeEchec.INCONNU, preuves, confiance=0.3, rapport=rapport,
            explication="le mouvement n'a pas pu être mesuré — ni confirmé, ni infirmé",
            reparations=("ASK_HUMAN",),
        )

    # ── 3. Le temps ─────────────────────────────────────────────────────
    if rapport.verdict_axe(Axe.TEMPOREL) is Verdict.ECHOUE:
        return _diagnostic(
            attendu, ModeEchec.DUREE_INCORRECTE, preuves, confiance=0.95,
            rapport=rapport,
            explication="la vidéo ne couvre pas la durée de la parole",
            reparations=("STRATEGY_FIX", "DECOMPOSITION"),
        )

    return None


def _diagnostic(attendu: Attendu, mode: ModeEchec, preuves: tuple[Ecart, ...],
                *, confiance: float, rapport: ObservationReport,
                explication: str = "",
                reparations: tuple[str, ...] = ()) -> FailureDiagnosis:
    return FailureDiagnosis(
        id=f"diagnostic_{attendu.shot_id}" if attendu.shot_id else "",
        shot_id=attendu.shot_id,
        mode=mode,
        severite=_severite(attendu.importance, mode),
        confiance=confiance,
        ecarts=preuves,
        preuves=tuple(m.nom for m in rapport.echecs),
        reparations_possibles=reparations,
        explication=explication,
    )
