"""Le rapport complet d'une vidéo : toutes les mesures en un seul objet.

Enchaîne les quatre analyses locales — métadonnées, coupes, son, image, voix —
puis en tire l'ADN, c'est-à-dire les contraintes de production. Rien ici ne
coûte d'argent : ffmpeg et numpy, sur la machine.

Le rapport est enregistré en base dans `structures`. C'est ce qui permet
d'analyser une vidéo une fois et de produire dix épisodes à partir de sa forme
sans jamais relancer l'analyse.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from pdz import db
from pdz.analyse import coupes, son, sonde, visuel, voix
from pdz.analyse.adn import Adn, extraire
from pdz.moteur.erreurs import ErreurPdz

log = logging.getLogger(__name__)


@dataclass
class Rapport:
    source: Path
    meta: sonde.Metadonnees
    decoupage: coupes.Decoupage
    son: son.AnalyseSon
    visuel: visuel.AnalyseVisuelle
    adn: Adn
    profil_voix: voix.ProfilVoix | None = None
    duree_analyse_s: float = 0.0

    def resume(self) -> str:
        lignes = [
            f"{self.source.name} — {self.meta.duree_s:.1f} s, "
            f"{self.meta.largeur}×{self.meta.hauteur} ({self.meta.ratio}), "
            f"{self.meta.fps:.0f} ips",
            f"Coupes  : {self.decoupage.resume()}",
            f"Son     : {self.son.energie_moyenne:.2f} d'énergie moyenne, "
            f"{self.son.ratio_silence:.0%} de silence"
            + (f", {self.son.tempo_bpm:.0f} BPM (confiance "
               f"{self.son.confiance_tempo:.2f})" if self.son.tempo_bpm else ""),
            f"Image   : {self.visuel.resume()}",
        ]
        if self.profil_voix is not None:
            lignes.append(f"Voix    : {self.profil_voix.resume()}")
        lignes.append(f"ADN     : {self.adn.resume()}")
        return "\n".join(lignes)

    def en_dict(self) -> dict:
        """Forme sérialisable, pour la base et pour un export JSON."""
        return {
            "source": str(self.source),
            "meta": {
                "duree_s": self.meta.duree_s, "largeur": self.meta.largeur,
                "hauteur": self.meta.hauteur, "fps": self.meta.fps,
                "ratio": self.meta.ratio, "a_du_son": self.meta.a_du_son,
            },
            "coupes": {
                "seuil": self.decoupage.seuil,
                "nb_plans": self.decoupage.nb_plans,
                "duree_mediane": round(self.decoupage.duree_mediane, 3),
                "coupes_par_minute": round(self.decoupage.coupes_par_minute, 2),
                "confiance": self.decoupage.confiance,
                "instants": [round(c, 2) for c in self.decoupage.coupes],
                "candidats": self.decoupage.candidats,
            },
            "son": {
                "courbe_energie": self.son.courbe_reduite(12),
                "ratio_silence": round(self.son.ratio_silence, 3),
                "tempo_bpm": self.son.tempo_bpm,
                "confiance_tempo": self.son.confiance_tempo,
                "lufs_estime": self.son.lufs_estime,
            },
            "visuel": {
                "palette": self.visuel.palette_hex,
                "luminosite": self.visuel.luminosite,
                "contraste": self.visuel.contraste,
                "saturation": self.visuel.saturation,
                "temperature": self.visuel.temperature,
                "nettete": self.visuel.nettete,
                "grain": self.visuel.grain,
                "plan": self.visuel.plan,
                "cadrage": self.visuel.cadrage,
                "densite_mouvement": self.visuel.densite_mouvement,
                "confiance": self.visuel.confiance,
                "images_cles": [str(p) for p in self.visuel.images_cles],
            },
            "voix": None if self.profil_voix is None else {
                "hauteur_hz": self.profil_voix.hauteur_hz,
                "registre": self.profil_voix.registre,
                "etendue_demi_tons": self.profil_voix.etendue_demi_tons,
                "timbre_hz": self.profil_voix.timbre_hz,
                "debit_syllabes_s": self.profil_voix.debit_syllabes_s,
                "confiance": self.profil_voix.confiance,
            },
            # `contraintes` est la lecture confortable ; `adn` est l'état
            # complet, seul capable de reconstruire l'objet pour une AUTRE
            # durée cible que celle de la vidéo de référence.
            "contraintes": self.adn.contraintes(),
            "adn": self.adn.en_dict(),
            "confiance": self.adn.confiance,
            "limites": self.adn.limites(),
        }


def analyser(chemin: Path, *, dossier_travail: Path | None = None,
             avec_voix: bool = True, images_cles: int = 6,
             seuil_force: float | None = None) -> Rapport:
    """Analyse complète d'une vidéo. Quelques secondes, zéro euro."""
    chemin = Path(chemin)
    debut = time.perf_counter()

    meta = sonde.sonder(chemin)
    log.info("Sonde : %.1f s, %d×%d, %s", meta.duree_s, meta.largeur,
             meta.hauteur, meta.ratio)

    decoupage = coupes.detecter(chemin, meta.duree_s, seuil_force=seuil_force)
    log.info("Coupes : %s", decoupage.resume())

    if not meta.a_du_son:
        raise ErreurPdz(
            f"{chemin.name} n'a pas de piste audio. Le rythme et le débit — "
            "ce qui se transfère le mieux — s'y trouvent : sans son, "
            "l'analyse n'aurait presque rien à dire."
        )

    analyse_son = son.analyser(chemin)

    analyse_visuelle = visuel.analyser(
        chemin, meta.duree_s, coupes=decoupage.coupes,
        dossier_images=(dossier_travail / "images_cles") if dossier_travail else None,
        combien=images_cles,
    )
    log.info("Image : %s", analyse_visuelle.resume())

    profil = None
    if avec_voix:
        try:
            profil = voix.analyser(chemin)
            log.info("Voix : %s", profil.resume())
        except ErreurPdz as e:
            # Pas de voix, ou musique seule : ce n'est pas une erreur de
            # l'utilisateur. On continue sans, et le débit retombe sur la
            # valeur de référence — avec une confiance qui le dit.
            log.info("Pas de voix exploitable (%s) : analyse poursuivie sans.", e)

    adn = extraire(decoupage, analyse_son, analyse_visuelle, profil)

    return Rapport(
        source=chemin, meta=meta, decoupage=decoupage, son=analyse_son,
        visuel=analyse_visuelle, adn=adn, profil_voix=profil,
        duree_analyse_s=round(time.perf_counter() - debut, 2),
    )


def enregistrer(rapport: Rapport, nom: str | None = None) -> str:
    """Écrit le rapport dans `structures`. Renvoie son identifiant."""
    structure_id = db.nouvel_id("str")
    donnees = rapport.en_dict()
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO structures (id, nom, source, mesures, confiance, cree_le)"
            " VALUES (?,?,?,?,?,?)",
            (structure_id, nom or rapport.source.stem, str(rapport.source),
             db.vider(donnees), db.vider(rapport.adn.confiance), db.maintenant()),
        )
    return structure_id


def charger(structure_id: str) -> dict:
    with db.connexion() as conn:
        ligne = conn.execute(
            "SELECT mesures FROM structures WHERE id = ?", (structure_id,)
        ).fetchone()
    if ligne is None:
        raise ErreurPdz(f"Structure introuvable : {structure_id}")
    return json.loads(ligne["mesures"])
