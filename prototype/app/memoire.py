"""La memoire : ce qui a marche, garde, et rendu au prochain plan.

Jusqu'ici chaque sujet repartait de zero. Le systeme etait aussi bon au run 50
qu'au run 5, et tout ce qu'il avait appris finissait dans un dossier.

Or on sait maintenant, pour chaque plan produit : la phrase, ce qu'il fallait
faire comprendre, l'action choisie, et — quand la video existe — ce qu'un
spectateur aveugle en a compris. C'est une banque de plans qui ont marche.

Au moment d'aligner un nouveau plan, on lui glisse deux ou trois plans passes
dont la phrase ressemble a la sienne et QUI ONT ETE COMPRIS. Rien d'autre :
un plan dont on ne sait pas s'il a marche n'apprend rien a personne.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path

from . import config

#: On ne retient que les plans dont le juge aveugle dit qu'ils sont compris.
NOTE_RETENUE = 0.7
#: Assez proche pour eclairer, sinon c'est du bruit.
RESSEMBLANCE_MINIMALE = 0.25
#: Trois exemples : au-dela on remplit le prompt au lieu de l'aider.
EXEMPLES_PAR_PLAN = 3

CHAMPS = ("subject", "voice", "educational_function", "understanding",
          "chosen", "mute_test", "understood")


@dataclass
class Souvenir:
    subject: str
    voice: str
    educational_function: str
    understanding: str
    chosen: str
    mute_test: float
    understood: float

    def as_bloc(self) -> str:
        return (f"· la phrase disait : « {self.voice} »\n"
                f"  il fallait faire comprendre : {self.understanding}\n"
                f"  l'action retenue : {self.chosen}\n"
                f"  comprise sans le son : {self.understood}")


def fichier() -> Path:
    return config.OUTPUT_DIR / "memoire" / "plans.json"


def charger() -> list[Souvenir]:
    chemin = fichier()
    if not chemin.is_file():
        return []
    try:
        brut = json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(brut, list):
        return []
    souvenirs = []
    for entree in brut:
        if not isinstance(entree, dict):
            continue
        if any(entree.get(c) is None for c in CHAMPS):
            continue
        try:
            souvenirs.append(Souvenir(**{c: entree[c] for c in CHAMPS}))
        except TypeError:
            continue
    return souvenirs


def retenir(souvenirs: list[Souvenir]) -> Path:
    """Ajoute a la banque, sans jamais y remettre deux fois le meme plan."""
    chemin = fichier()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    existants = charger()
    connus = {(s.subject, s.voice) for s in existants}
    nouveaux = [s for s in souvenirs
                if s.understood >= NOTE_RETENUE and (s.subject, s.voice) not in connus]
    if nouveaux:
        tout = existants + nouveaux
        chemin.write_text(
            json.dumps([asdict(s) for s in tout], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
    return chemin


def exemples(voice: str, educational_function: str, sujet_courant: str = "",
             combien: int = EXEMPLES_PAR_PLAN) -> list[Souvenir]:
    """Les plans passes qui ressemblent a celui-la, les mieux compris d'abord.

    On ecarte le sujet courant : un plan a le droit d'apprendre d'une autre
    video, pas de se recopier lui-meme.
    """
    cible = f"{voice} {educational_function}".lower()
    notes = []
    for s in charger():
        if sujet_courant and s.subject == sujet_courant:
            continue
        proche = SequenceMatcher(
            None, cible, f"{s.voice} {s.educational_function}".lower()).ratio()
        if proche >= RESSEMBLANCE_MINIMALE:
            notes.append((proche * s.understood, s))
    notes.sort(key=lambda n: n[0], reverse=True)
    return [s for _, s in notes[:combien]]


def bloc(souvenirs: list[Souvenir]) -> str:
    """Ce qu'on donne a lire a l'agent. Vide s'il n'y a rien a montrer."""
    if not souvenirs:
        return ""
    return "\n".join(s.as_bloc() for s in souvenirs)


def moisson(subject: str, shots, alignements: dict, verdicts: dict) -> list[Souvenir]:
    """Ce qu'un run laisse a la memoire : les plans compris, et eux seuls."""
    recolte = []
    for shot in shots:
        alignement = alignements.get(shot.id)
        verdict = verdicts.get(shot.id)
        if not alignement or not verdict:
            continue
        recolte.append(Souvenir(
            subject=subject,
            voice=shot.voice,
            educational_function=shot.educational_function,
            understanding=str(alignement.get("understanding") or "").strip(),
            chosen=str(alignement.get("chosen") or "").strip(),
            mute_test=float(alignement.get("mute_test") or 0.0),
            understood=float(verdict.get("understood") or 0.0)))
    return [s for s in recolte if s.understanding and s.chosen]
