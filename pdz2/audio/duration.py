"""Négociation de durée : tenir la commande sans jamais falsifier la mesure.

Le problème que ce module résout était une incohérence silencieuse. Un épisode
commandé à 40 s en livrait 27,4, le MP4 était techniquement parfait, et aucune
décision n'était prise ni inscrite nulle part.

Le seul levier honnête est le **débit de parole**. Il ne fabrique pas de
contenu, il ne rallonge pas artificiellement une timeline, il ne touche pas à
la mesure : il change ce que la voix fait réellement, puis on mesure le
résultat comme d'habitude.

    TTS réel → durée réelle → VoiceTimeline → découpage temporel

reste la seule chaîne. Ce module s'insère **avant** elle, pas à sa place : il
choisit un réglage de voix, puis la synthèse et la mesure suivent leur cours.

## Pourquoi une calibration plutôt qu'un modèle

Choisir le débit à partir de l'estimation du script reviendrait à faire d'une
approximation la base d'une décision. Ce module ne lit aucune estimation. Il
**synthétise réellement** le texte au débit de référence, mesure les trames du
WAV obtenu, et déduit le débit nécessaire de cette mesure. Le moteur employé
ici tourne à plus de 250 fois le temps réel : la calibration coûte une
fraction de seconde. Ce module ne le nomme pas — il ne connaît que le port.

## La bande naturelle, mesurée

Relevé sur le script de l'épisode de référence (82 mots, 502 caractères) :

    80 wpm → 50.92 s      140 wpm → 29.93 s
   100 wpm → 42.58 s      165 wpm → 24.93 s
   120 wpm → 35.20 s      190 wpm → 21.41 s
                          220 wpm → 18.39 s

## Le biais connu de la calibration

La calibration synthétise le script **d'un trait**, alors que la narration
définitive enchaîne les répliques une à une, avec un silence entre chacune.
La calibration sous-estime donc le total, systématiquement.

Mesuré sur l'épisode de référence (8 répliques) : 41,86 s calibrées pour
44,47 s réellement mesurées, soit +6,2 %, c'est-à-dire environ un tiers de
seconde par jointure. L'écart est du bon côté — on ne promet jamais plus court
que ce qui sortira — et reste très en deçà de la tolérance de 15 %. Le corriger
demanderait de connaître les silences avant de les produire ; la durée
officielle, elle, reste celle que `VoiceTimeline` mesure sur l'audio définitif.

La durée varie bien en raison inverse du débit. La bande retenue est
`[120, 200]` : en deçà la parole traîne au point de s'entendre, au-delà elle
se précipite. Hors de cette bande, le compilateur refuse d'ajuster et déclare
que c'est le **contenu** qui ne convient pas — ce qui est vrai, et ce qu'aucun
réglage de voix ne corrigera.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pdz2.audio.ports import SpeechSynthesiser, VoiceSpec
from pdz2.audio.wave_io import measure_wav
from pdz2.contracts.script import DurationDecision, DurationPolicy, ScriptState

__all__ = [
    "DurationNegotiator",
    "NATURAL_RATE_MIN_WPM",
    "NATURAL_RATE_MAX_WPM",
    "DEFAULT_TOLERANCE",
]

NATURAL_RATE_MIN_WPM = 120
"""En deçà, la parole traîne — mesuré : 35,2 s là où 165 wpm en donne 24,9."""

NATURAL_RATE_MAX_WPM = 200
"""Au-delà, elle se précipite et la lisibilité des images en pâtit."""

DEFAULT_TOLERANCE = 0.15
"""Sur 40 s commandées, un livrable entre 34 et 46 s reste le même objet."""


@dataclass
class DurationNegotiator:
    """Choisit un débit de voix pour tenir la commande, ou dit pourquoi non."""

    synthesiser: SpeechSynthesiser
    tolerance: float = DEFAULT_TOLERANCE
    rate_min_wpm: int = NATURAL_RATE_MIN_WPM
    rate_max_wpm: int = NATURAL_RATE_MAX_WPM
    notes: list[str] = field(default_factory=list)

    def negotiate(
        self,
        *,
        script: ScriptState,
        voice: VoiceSpec,
        requested_s: float | None,
        workdir: Path | None = None,
    ) -> DurationPolicy:
        calibree = self._calibrer(script, voice, workdir)
        reference = voice.rate_wpm

        if requested_s is None:
            return self._policy(
                script, reference, reference, calibree, None,
                DurationDecision.NO_TARGET, calibree,
                "aucune durée commandée : le débit de référence est conservé",
            )

        if abs(calibree - requested_s) <= requested_s * self.tolerance:
            return self._policy(
                script, reference, reference, calibree, requested_s,
                DurationDecision.ON_TARGET, calibree,
                f"le débit de référence donne {calibree:.1f}s pour "
                f"{requested_s:.0f}s commandées, dans la tolérance",
            )

        # Durée et débit varient en raison inverse : c'est ce que la mesure
        # montre, et c'est ce qui rend le débit visé calculable d'un trait.
        vise = int(round(reference * calibree / requested_s))
        borne = max(self.rate_min_wpm, min(self.rate_max_wpm, vise))
        projetee = round(reference * calibree / borne, 3)

        if borne == vise:
            return self._policy(
                script, reference, borne, calibree, requested_s,
                DurationDecision.RATE_ADJUSTED, projetee,
                f"débit porté de {reference} à {borne} mots/min : "
                f"{calibree:.1f}s mesurées deviennent {projetee:.1f}s visées",
            )

        manque = vise < self.rate_min_wpm
        decision = (
            DurationDecision.CONTENT_TOO_SHORT
            if manque
            else DurationDecision.CONTENT_TOO_LONG
        )
        return self._policy(
            script, reference, borne, calibree, requested_s,
            decision, projetee,
            f"tenir {requested_s:.0f}s exigerait {vise} mots/min, hors de la "
            f"bande naturelle [{self.rate_min_wpm}, {self.rate_max_wpm}] : "
            f"{'il manque du texte' if manque else 'il y a trop de texte'}. "
            f"Débit borné à {borne}, ce qui donnera environ {projetee:.1f}s. "
            "Aucun réglage de voix ne corrige un contenu de la mauvaise "
            "longueur — seul le script le peut.",
        )

    # ------------------------------------------------------------ calibration

    def _calibrer(
        self, script: ScriptState, voice: VoiceSpec, workdir: Path | None
    ) -> float:
        """Synthétise réellement le script, et mesure ce qui en sort."""
        texte = " ".join(line.text for line in script.lines)
        if not texte.strip():
            raise ValueError("script vide : rien à calibrer")
        cible = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="pdz2-cal-"))
        cible.mkdir(parents=True, exist_ok=True)
        sortie = cible / "calibration.wav"
        self.synthesiser.synthesise(texte, voice, sortie)
        mesure = measure_wav(sortie)
        self.notes.append(
            f"calibration : {len(script.lines)} répliques synthétisées à "
            f"{voice.rate_wpm} mots/min → {mesure.duration_s:.2f}s mesurées"
        )
        return round(mesure.duration_s, 3)

    def _policy(
        self, script, reference, choisi, calibree, requested, decision,
        projetee, raison,
    ) -> DurationPolicy:
        return DurationPolicy(
            script_state_id=script.id,
            requested_s=requested,
            calibrated_s=calibree,
            calibration_rate_wpm=reference,
            chosen_rate_wpm=choisi,
            tolerance=self.tolerance,
            decision=decision,
            rationale=raison,
            projected_s=projetee,
            parent_id=script.id,
        )
