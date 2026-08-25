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
    "RATE_EFFECT_FLOOR",
    "PROBE_SENTENCE",
]

NATURAL_RATE_MIN_WPM = 120
"""En deçà, la parole traîne — mesuré : 35,2 s là où 165 wpm en donne 24,9."""

NATURAL_RATE_MAX_WPM = 200
"""Au-delà, elle se précipite et la lisibilité des images en pâtit."""

DEFAULT_TOLERANCE = 0.15
"""Sur 40 s commandées, un livrable entre 34 et 46 s reste le même objet."""

PROBE_SENTENCE = "Une phrase courte, dite deux fois, à deux vitesses."
"""Texte de la sonde de contrôlabilité. Court : elle peut coûter un appel."""

RATE_EFFECT_FLOOR = 0.10
"""Écart relatif minimal entre les deux vitesses pour dire « le débit agit ».

Entre 120 et 200 mots/min, un moteur qui obéit rend un écart d'environ 40 %.
Un moteur qui ignore le réglage rend deux fois la même durée, à la gigue de
mesure près. Le seuil est placé très bas entre les deux : il ne s'agit pas de
noter l'obéissance, seulement de distinguer « agit » de « n'agit pas »."""


@dataclass
class DurationNegotiator:
    """Choisit un débit de voix pour tenir la commande, ou dit pourquoi non."""

    synthesiser: SpeechSynthesiser
    tolerance: float = DEFAULT_TOLERANCE
    rate_min_wpm: int = NATURAL_RATE_MIN_WPM
    rate_max_wpm: int = NATURAL_RATE_MAX_WPM
    notes: list[str] = field(default_factory=list)
    _controle: bool | None = field(default=None, repr=False)
    """Résultat mémorisé de la sonde de débit. `None` : pas encore sondé."""

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
        # Encore faut-il que le moteur obéisse au réglage — ce qui se vérifie,
        # et ne se suppose pas : tous ne l'exposent pas.
        vise = int(round(reference * calibree / requested_s))
        borne = max(self.rate_min_wpm, min(self.rate_max_wpm, vise))
        projetee = round(reference * calibree / borne, 3)

        if not self._debit_agit(voice, workdir):
            trop_long = calibree > requested_s
            return self._policy(
                script, reference, reference, calibree, requested_s,
                DurationDecision.CONTENT_TOO_LONG
                if trop_long
                else DurationDecision.CONTENT_TOO_SHORT,
                calibree,
                f"le moteur de voix ignore le débit — mesuré, pas supposé : "
                f"{PROBE_SENTENCE!r} dure la même chose à {self.rate_min_wpm} "
                f"et à {self.rate_max_wpm} mots/min. Le seul levier restant "
                f"est le texte : {calibree:.1f}s mesurées pour "
                f"{requested_s:.0f}s commandées, il y a "
                f"{'trop' if trop_long else 'trop peu'} de texte.",
            )

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

    # ---------------------------------------------------- sonde de débit

    def _debit_agit(self, voice: VoiceSpec, workdir: Path | None) -> bool:
        """Le moteur obéit-il vraiment au débit ? Deux synthèses le disent.

        Sans cette sonde, un moteur distant qui n'expose aucun réglage de
        vitesse laisserait le négociateur annoncer un débit « porté de 165 à
        190 » sans que rien ne change dans l'audio : une décision inscrite au
        contrat, et démentie par le fichier. La dégradation serait invisible.

        La sonde est mise en cache : elle ne dépend que du moteur, pas du
        script, et peut coûter un appel facturé.
        """
        if self._controle is not None:
            return self._controle

        cible = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="pdz2-son-"))
        cible.mkdir(parents=True, exist_ok=True)
        durees: list[float] = []
        for rate in (self.rate_min_wpm, self.rate_max_wpm):
            sortie = cible / f"sonde-{rate}.wav"
            self.synthesiser.synthesise(
                PROBE_SENTENCE,
                VoiceSpec(
                    voice_id=voice.voice_id,
                    rate_wpm=rate,
                    pitch=voice.pitch,
                    amplitude=voice.amplitude,
                    gap_ms=voice.gap_ms,
                ),
                sortie,
            )
            durees.append(measure_wav(sortie).duration_s)

        lent, rapide = durees
        ecart = abs(lent - rapide) / lent if lent > 0 else 0.0
        self._controle = ecart >= RATE_EFFECT_FLOOR
        self.notes.append(
            f"sonde de débit : {lent:.2f}s à {self.rate_min_wpm} mots/min contre "
            f"{rapide:.2f}s à {self.rate_max_wpm} — écart {ecart:.0%}, le moteur "
            + ("obéit au réglage" if self._controle else "l'ignore")
        )
        return self._controle

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
