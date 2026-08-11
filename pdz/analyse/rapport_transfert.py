"""Le rapport avant/après : de quoi juger si une empreinte créative transfère
la MÉCANIQUE d'une référence sur un sujet neuf, sans en copier le CONTENU.

Le test fondamental, tel que posé pour ce projet :

    SAME FUNCTION + NEW SUBJECT + NEW STORY + NEW VISUAL EXECUTION

Ce module ne le tranche jamais lui-même — « la mécanique a été transférée,
pas le contenu » reste un jugement humain, pas quelque chose qu'un script
peut décider à la place de la personne qui regarde. Il rassemble seulement,
côte à côte, l'AVANT (l'empreinte créative de la référence, et de quoi
parlait vraiment la vidéo si c'est noté) et l'APRÈS (le script produit sur
le sujet neuf), plus les vérifications qui, elles, sont mécaniquement
calculables :

  · SHOT_FUNCTION varie-t-il réellement d'un plan à l'autre, et se
    retrouve-t-il dans le prompt d'image envoyé au modèle ? (voir
    `pdz.production.images.prompt_plan`)
  · Le script généré partage-t-il des mots-clés avec le sujet ORIGINAL de
    la référence ? Un chevauchement fort est le signal mécanique le plus
    proche d'un contenu recopié plutôt que transféré — mais un
    chevauchement nul ne prouve pas, à lui seul, que la mécanique a
    réellement pris.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Mots trop communs pour signaler quoi que ce soit s'ils se répètent entre
# deux textes. Courte à dessein : le but est d'écarter le bruit grammatical
# évident, pas de construire un filtre linguistique complet.
_MOTS_VIDES = {
    "alors", "apres", "avant", "avec", "cela", "ceux", "chaque", "comme",
    "dans", "depuis", "elle", "elles", "encore", "entre", "etait", "etre",
    "faire", "fait", "juste", "leur", "leurs", "mais", "meme", "nous",
    "notre", "nos", "ont", "ou", "pas", "peu", "peut", "plus", "pour",
    "quand", "que", "quel", "quelle", "qui", "sans", "sont", "sous", "sur",
    "tous", "toute", "toutes", "tout", "tres", "une", "vers", "vous",
}


def _normaliser(mot: str) -> str:
    """Minuscule, sans accent — « révèle » et « revele » sont le même mot."""
    sans_accent = unicodedata.normalize("NFKD", mot).encode("ascii", "ignore").decode()
    return sans_accent.lower()


def mots_significatifs(texte: str) -> set[str]:
    """Les mots d'un texte qui porteraient un chevauchement réel s'ils se
    retrouvaient dans un autre texte. Une comparaison mot à mot plutôt que
    phrase à phrase : la reformulation ne trompe pas le calcul, contrairement
    à une comparaison de chaînes."""
    bruts = re.findall(r"[a-zA-ZÀ-ÿ]{4,}", texte)
    return {m for m in (_normaliser(b) for b in bruts) if m not in _MOTS_VIDES}


def chevauchement_lexical(reference: str, obtenu: str) -> set[str]:
    """Les mots significatifs partagés entre deux textes."""
    if not reference.strip():
        return set()
    return mots_significatifs(reference) & mots_significatifs(obtenu)


@dataclass
class PlanRapporte:
    """Un plan du script généré, tel qu'il a réellement été mis en image."""

    numero: int
    personnage: str
    replique: str
    action: str
    fonction: str
    prompt_image: str


@dataclass
class RapportTransfert:
    reference_id: str
    sujet_nouveau: str
    empreinte_texte: str
    mecanique_attendue: str
    sujet_original: str
    titre_script: str
    plans: list[PlanRapporte] = field(default_factory=list)

    def fonctions_consecutives_identiques(self) -> int:
        """Compte les paires de plans voisins qui partagent la même fonction.

        Le prompt du scénariste l'interdit explicitement (« deux plans
        consécutifs ne partagent jamais la même fonction ») : c'est ce qui
        évite « trois plans de ville qui se ressemblent ». Une valeur non
        nulle ici est une régression mesurable, pas une question de goût.
        """
        paires = zip(self.plans, self.plans[1:])
        return sum(1 for a, b in paires if a.fonction and a.fonction == b.fonction)

    def fonctions_distinctes(self) -> int:
        return len({p.fonction for p in self.plans if p.fonction})

    def prompts_distincts(self) -> int:
        return len({p.prompt_image for p in self.plans})

    def chevauchement_avec_sujet_original(self) -> set[str]:
        texte_script = " ".join(f"{p.replique} {p.action}" for p in self.plans)
        return chevauchement_lexical(self.sujet_original, texte_script)


def construire_rapport(r: RapportTransfert) -> str:
    """Le rapport en Markdown — lisible tel quel, ou déposé dans un fichier."""
    lignes = [
        f"# Rapport avant/après — {r.reference_id} → « {r.sujet_nouveau} »",
        "",
        "Ce rapport ne conclut rien à ta place. « La mécanique a été "
        "transférée, pas le contenu » reste un jugement humain — voici de "
        "quoi le faire vite.",
        "",
        "## AVANT — l'empreinte créative de la référence",
        "",
    ]

    if r.mecanique_attendue:
        lignes += [f"**Mécanique attendue (notée à la main avant analyse) :** "
                   f"{r.mecanique_attendue}", ""]
    if r.sujet_original:
        lignes += [f"**Sujet original de la référence :** {r.sujet_original}", ""]

    lignes += [
        "**Ce que le scénariste a reçu** (seuls les champs à confiance "
        "suffisante ; le reste n'est jamais devenu une contrainte) :",
        "```",
        r.empreinte_texte or "(rien — confiance trop faible partout, ou pas d'empreinte)",
        "```",
        "",
        "## APRÈS — le script produit sur le sujet neuf",
        "",
        f"Sujet demandé : **{r.sujet_nouveau}**",
        f"Titre généré : *{r.titre_script}*" if r.titre_script else "",
        "",
        "| # | Perso | Réplique | Action | SHOT_FUNCTION | Prompt image |",
        "|---|---|---|---|---|---|",
    ]
    for p in r.plans:
        lignes.append(
            f"| {p.numero} | {p.personnage} | {p.replique} | {p.action} | "
            f"{p.fonction} | `{p.prompt_image}` |"
        )

    lignes += ["", "## Vérifications mécaniques (calculées, pas jugées)", ""]

    n = len(r.plans)
    consec = r.fonctions_consecutives_identiques()
    lignes.append(
        f"- **SHOT_FUNCTION varie d'un plan à l'autre** : "
        f"{r.fonctions_distinctes()} fonctions distinctes sur {n} plans, "
        f"{consec} paire(s) consécutive(s) identique(s) "
        f"({'✓ conforme à la règle' if consec == 0 else '✗ à regarder'})."
    )
    lignes.append(
        f"- **SHOT_FUNCTION atteint le prompt d'image** : "
        f"{r.prompts_distincts()} prompts distincts sur {n} plans."
    )

    if r.sujet_original:
        partages = r.chevauchement_avec_sujet_original()
        if partages:
            lignes.append(
                f"- **Chevauchement lexical avec le sujet ORIGINAL de la "
                f"référence** : {len(partages)} mot(s) partagé(s) — "
                f"{', '.join(sorted(partages))}. À regarder : un contenu "
                "transféré plutôt que recopié n'a normalement presque rien "
                "en commun avec le sujet d'origine."
            )
        else:
            lignes.append(
                "- **Chevauchement lexical avec le sujet ORIGINAL de la "
                "référence** : aucun mot significatif partagé. Signal "
                "favorable, mais ne prouve pas à lui seul que la mécanique "
                "a réellement pris — voir la checklist ci-dessous."
            )
    else:
        lignes.append(
            "- **Chevauchement lexical** : pas de `sujet_original` noté "
            "pour cette référence — vérification sautée. Ajoute-le dans "
            "le `.yaml` à côté de la vidéo pour l'activer."
        )

    lignes += [
        "",
        "## Checklist humaine — le test fondamental",
        "",
        "> SAME FUNCTION + NEW SUBJECT + NEW STORY + NEW VISUAL EXECUTION",
        "",
        "- [ ] Le hook du script reprend-il le MÉCANISME de l'accroche de la "
        "référence (même type de question, même promesse) sur un sujet "
        "totalement différent ?",
        "- [ ] La structure narrative (escalade, fin) suit-elle le même "
        "schéma, avec une histoire différente ?",
        "- [ ] Aucune réplique ne mentionne, même indirectement, le sujet "
        "réel de la vidéo de référence ?",
        "- [ ] Les SHOT_FUNCTION ci-dessus produisent des plans qu'on "
        "reconnaîtrait comme suivant la même logique de montage que la "
        "référence, sur une exécution visuelle différente ?",
    ]
    return "\n".join(lignes)
