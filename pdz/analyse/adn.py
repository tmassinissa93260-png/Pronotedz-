"""L'ADN d'une vidéo : transformer des mesures en **contraintes de production**.

Le trou qui restait dans la chaîne. On savait mesurer une vidéo de référence
(coupes, son, image) ; on ne savait pas quoi en faire. Ce module fait la
traduction, et il la fait en Python, pas avec un modèle : passer des nombres
exacts à un LLM pour qu'il en ressorte d'autres nombres, c'est payer pour
dégrader une information qu'on avait déjà.

    médiane des plans = 1,4 s          →  environ 2 plans par réplique
    débit = 5,8 syllabes/s             →  199 mots/minute, donc 12 mots/réplique
    pics d'énergie à 18 %, 47 %, 79 %  →  relances à ces trois endroits
    palette + contraste + grain        →  consignes d'image

Ce qui se transfère et ce qui ne se transfère pas est explicite. La **forme**
d'une vidéo se copie : rythme, débit, densité de coupes, palette. Ce qui a
fait qu'elle a marché ne se copie pas — on ne voit que les vidéos qui ont
percé, jamais les milliers d'identiques qui n'ont rien fait. C'est écrit dans
`limites()`, et cette liste part avec le rapport plutôt que d'être passée sous
silence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from pdz.analyse.coupes import Decoupage
from pdz.analyse.son import AnalyseSon
from pdz.analyse.visuel import AnalyseVisuelle
from pdz.analyse.voix import ProfilVoix

# Français parlé : environ 1,75 syllabe par mot, tous textes confondus.
# C'est le pont entre ce qu'on sait mesurer (des syllabes) et ce dont le
# scénariste a besoin (des mots).
SYLLABES_PAR_MOT = 1.75

# Une réplique occupe en moyenne ce nombre de plans : le personnage qui parle,
# puis la réaction de l'autre. Voir le bloc « réplique ≠ plan » de agents/base.
PLANS_PAR_REPLIQUE = 2.0

# Bornes de sécurité. Une référence au montage extrême (0,4 s par plan) donne
# des contraintes intenables en production : 100 images pour 45 secondes.
DUREE_PLAN_MIN, DUREE_PLAN_MAX = 0.8, 4.0
DEBIT_MIN_WPM, DEBIT_MAX_WPM = 110, 230


@dataclass
class Adn:
    """Ce qu'on a mesuré, traduit en instructions de fabrication."""

    duree_s: float

    # ── Rythme ───────────────────────────────────────────────────────────
    duree_plan_s: float
    coupes_par_minute: float
    duree_premier_plan_s: float
    plans_par_replique: float

    # ── Parole ───────────────────────────────────────────────────────────
    debit_wpm: int
    ratio_parole: float

    # ── Structure ────────────────────────────────────────────────────────
    relances_pct: list[float]        # positions, en part de la durée
    courbe_energie: list[float]      # 12 points

    # ── Image ────────────────────────────────────────────────────────────
    palette: list[str]
    consignes_image: list[str]

    confiance: dict[str, float] = field(default_factory=dict)

    # ── Ce qui en sort ───────────────────────────────────────────────────

    def nb_repliques(self, duree_cible_s: float | None = None) -> int:
        duree = duree_cible_s or self.duree_s
        secondes_par_replique = self.duree_plan_s * self.plans_par_replique
        return max(3, round(duree / max(0.8, secondes_par_replique)))

    def mots_par_replique(self, duree_cible_s: float | None = None) -> list[int]:
        duree = duree_cible_s or self.duree_s
        n = self.nb_repliques(duree)
        par_replique = duree / n
        return [max(4, round(par_replique * self.debit_wpm / 60)) for _ in range(n)]

    def nb_plans(self, duree_cible_s: float | None = None) -> int:
        duree = duree_cible_s or self.duree_s
        return max(4, round(duree / self.duree_plan_s))

    def repliques_de_relance(self, duree_cible_s: float | None = None) -> list[int]:
        """Sur quelles répliques placer les relances, en numéros.

        Les positions viennent des pics d'énergie de la référence : là où elle
        remontait le son, c'est là qu'elle relançait l'attention.
        """
        n = self.nb_repliques(duree_cible_s)
        numeros = sorted({min(n, max(2, round(p * n))) for p in self.relances_pct})
        return [x for x in numeros if x > 1]

    def contraintes(self, duree_cible_s: float | None = None) -> dict[str, Any]:
        """Le bloc passé au scénariste. Tout y est chiffré et justifié."""
        duree = duree_cible_s or self.duree_s
        return {
            "duree_s": round(duree, 1),
            "nb_repliques": self.nb_repliques(duree),
            "mots_par_replique": self.mots_par_replique(duree),
            "nb_plans_vises": self.nb_plans(duree),
            "debit_wpm": self.debit_wpm,
            "duree_plan_s": round(self.duree_plan_s, 2),
            "repliques_de_relance": self.repliques_de_relance(duree),
            "duree_hook_s": round(self.duree_premier_plan_s, 2),
        }

    def resume(self) -> str:
        return (
            f"{self.duree_s:.0f} s · plan médian {self.duree_plan_s:.2f} s "
            f"({self.coupes_par_minute:.0f} coupes/min) · "
            f"débit {self.debit_wpm} mots/min · "
            f"parole {self.ratio_parole:.0%} · "
            f"{len(self.relances_pct)} relances · "
            f"palette {' '.join(self.palette[:3])}"
        )

    def limites(self) -> list[str]:
        """Ce que cette analyse **ne** dit **pas**. Toujours affiché avec elle.

        Sans cette liste, un rapport chiffré donne l'illusion d'expliquer un
        succès qu'il ne fait que décrire.
        """
        limites = [
            "La forme se mesure, la réussite ne s'explique pas : on n'observe "
            "que les vidéos qui ont percé, jamais les milliers d'identiques "
            "qui n'ont rien fait.",
            "Rien ici ne dit à quel moment les gens décrochaient : la courbe "
            "de rétention n'est pas dans le fichier vidéo.",
            "Le sujet et l'écriture — ce qui compte le plus — ne sont pas "
            "transférés. Seule la forme l'est.",
        ]
        for nom, valeur in sorted(self.confiance.items()):
            if valeur < 0.6:
                limites.append(
                    f"Mesure « {nom} » peu fiable ({valeur:.2f}) : à traiter "
                    "comme un ordre de grandeur, pas comme une consigne."
                )
        return limites

    # ── Aller-retour avec la base ────────────────────────────────────────

    def en_dict(self) -> dict[str, Any]:
        """Tous les champs, pour pouvoir reconstruire l'ADN à l'identique.

        On stocke l'état, pas les valeurs dérivées : `contraintes()` dépend de
        la durée visée, qui n'est pas connue au moment de l'analyse. Stocker
        son résultat figerait l'ADN sur la durée de la vidéo de référence.
        """
        return {
            "duree_s": self.duree_s,
            "duree_plan_s": self.duree_plan_s,
            "coupes_par_minute": self.coupes_par_minute,
            "duree_premier_plan_s": self.duree_premier_plan_s,
            "plans_par_replique": self.plans_par_replique,
            "debit_wpm": self.debit_wpm,
            "ratio_parole": self.ratio_parole,
            "relances_pct": self.relances_pct,
            "courbe_energie": self.courbe_energie,
            "palette": self.palette,
            "consignes_image": self.consignes_image,
            "confiance": self.confiance,
        }

    @classmethod
    def depuis_dict(cls, donnees: dict[str, Any]) -> Adn:
        return cls(**{k: donnees[k] for k in donnees if k in cls.__annotations__})

    def bloc_pour_prompt(self) -> str:
        return "\n".join([
            f"Durée du plan médian : {self.duree_plan_s:.2f} s "
            f"({self.coupes_par_minute:.0f} coupes/minute)",
            f"Premier plan (le hook) : {self.duree_premier_plan_s:.2f} s",
            f"Débit de parole : {self.debit_wpm} mots/minute",
            f"Part parlée : {self.ratio_parole:.0%} de la durée",
            f"Relances aux positions : "
            f"{', '.join(f'{p:.0%}' for p in self.relances_pct) or 'aucune détectée'}",
            f"Courbe d'énergie (12 points) : {self.courbe_energie}",
        ])


# ── Extraction ───────────────────────────────────────────────────────────

def _pics(courbe: list[float], mini_ecart: int = 2) -> list[float]:
    """Positions des remontées d'énergie, en part de la durée.

    On ne garde qu'un sommet séparé du précédent : deux pics collés sont le
    même événement vu deux fois, et donneraient deux relances au même endroit.
    """
    if len(courbe) < 5:
        return []

    a = np.array(courbe, dtype=np.float64)
    seuil = float(np.median(a)) + float(np.std(a)) * 0.5

    positions: list[int] = []
    for i in range(1, a.size - 1):
        if a[i] >= a[i - 1] and a[i] > a[i + 1] and a[i] > seuil:
            if not positions or i - positions[-1] >= mini_ecart:
                positions.append(i)

    # Le tout début n'est pas une relance : c'est le hook, il est déjà traité.
    return [round(i / (a.size - 1), 3) for i in positions if i / (a.size - 1) > 0.15]


def extraire(decoupage: Decoupage, son: AnalyseSon,
             visuel: AnalyseVisuelle | None = None,
             profil_voix: ProfilVoix | None = None) -> Adn:
    """Assemble les mesures en contraintes de production."""
    duree_plan = float(np.clip(decoupage.duree_mediane, DUREE_PLAN_MIN, DUREE_PLAN_MAX))

    # Débit : mesuré si on a analysé la voix, sinon la valeur de référence du
    # français parlé médiatique. On ne fabrique pas un chiffre précis quand on
    # n'a pas la mesure — on prend une norme, et on le dit dans la confiance.
    if profil_voix and profil_voix.debit_syllabes_s > 0:
        debit = profil_voix.debit_syllabes_s * 60 / SYLLABES_PAR_MOT
        confiance_debit = profil_voix.confiance
    else:
        debit, confiance_debit = 165.0, 0.4

    premier_plan = decoupage.durees[0] if decoupage.durees else duree_plan
    courbe = son.courbe_reduite(12)

    consignes: list[str] = []
    palette: list[str] = []
    if visuel is not None:
        palette = visuel.palette_hex[:5]
        consignes = _consignes_image(visuel)

    confiance = {
        "decoupage": decoupage.confiance,
        "debit": round(confiance_debit, 2),
        "tempo": son.confiance_tempo,
    }
    if visuel is not None:
        confiance["style_visuel"] = visuel.confiance

    return Adn(
        duree_s=round(decoupage.duree_totale, 2),
        duree_plan_s=round(duree_plan, 2),
        coupes_par_minute=round(decoupage.coupes_par_minute, 1),
        duree_premier_plan_s=round(float(premier_plan), 2),
        plans_par_replique=PLANS_PAR_REPLIQUE,
        debit_wpm=int(np.clip(round(debit), DEBIT_MIN_WPM, DEBIT_MAX_WPM)),
        # La part parlée vient de l'analyse de voix quand on l'a : elle
        # distingue la parole du reste. `1 - ratio_silence` compte la musique
        # comme de la parole, ce qui donne 100 % sur un clip musical.
        ratio_parole=round(
            profil_voix.ratio_parole if profil_voix else 1.0 - son.ratio_silence, 3
        ),
        relances_pct=_pics(courbe),
        courbe_energie=courbe,
        palette=palette,
        consignes_image=consignes,
        confiance=confiance,
    )


def _consignes_image(v: AnalyseVisuelle) -> list[str]:
    """Traduit les mesures d'image en bouts de prompt, en anglais.

    Ces fragments sont ajoutés à chaque prompt d'image. Ils ne remplacent pas
    le style de l'univers : ils l'accordent à la référence mesurée.
    """
    consignes: list[str] = []

    if v.contraste > 0.28:
        consignes.append("high contrast, deep blacks")
    elif v.contraste < 0.14:
        consignes.append("low contrast, soft flat tones")

    if v.saturation > 0.55:
        consignes.append("highly saturated colors")
    elif v.saturation < 0.20:
        consignes.append("desaturated, muted palette")

    if v.temperature > 0.10:
        consignes.append("warm color grade")
    elif v.temperature < -0.10:
        consignes.append("cool color grade")

    if v.grain > 0.35:
        consignes.append("visible film grain")
    elif v.nettete > 0.55:
        consignes.append("crisp clean edges, no grain")

    if v.luminosite < 0.35:
        consignes.append("dark low-key lighting")
    elif v.luminosite > 0.65:
        consignes.append("bright high-key lighting")

    plan = {"gros plan": "close-up framing",
            "plan rapproché": "medium close-up framing",
            "plan moyen": "medium shot framing",
            "plan large": "wide shot framing"}[v.plan]
    consignes.append(plan)
    return consignes
