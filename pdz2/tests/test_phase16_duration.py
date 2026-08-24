"""Négociation de durée : tenir la commande sans falsifier la mesure.

L'incohérence d'origine était silencieuse : 40 s commandées, 27,4 s livrées,
MP4 parfait, aucune décision nulle part. Ces tests fixent les quatre grandeurs
que rien ne doit confondre — commandée, calibrée, tolérance, décision — et le
fait que le seul levier employé soit le débit de parole, mesuré.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.audio.duration import (
    NATURAL_RATE_MAX_WPM,
    NATURAL_RATE_MIN_WPM,
    DurationNegotiator,
)
from pdz2.audio.espeak import EspeakSynthesiser
from pdz2.audio.ports import VoiceSpec
from pdz2.contracts.script import DurationDecision, DurationPolicy
from pdz2.tests import pipeline

needs_espeak = pytest.mark.skipif(
    not EspeakSynthesiser().get_capabilities().usable, reason="eSpeak NG absent"
)


@pytest.fixture(scope="module")
def script():
    import tempfile
    from pathlib import Path

    return pipeline.build_episode(Path(tempfile.mkdtemp(prefix="phase16-"))).script


def _negocier(script, requested, tmp_path, **kwargs):
    return DurationNegotiator(synthesiser=EspeakSynthesiser(), **kwargs).negotiate(
        script=script,
        voice=VoiceSpec(voice_id="fr", rate_wpm=165),
        requested_s=requested,
        workdir=tmp_path,
    )


# ------------------------------------------------------- la calibration est réelle


@needs_espeak
def test_the_calibration_is_a_real_synthesis_not_an_estimate(script, tmp_path):
    """La décision s'appuie sur des trames mesurées, pas sur un modèle."""
    policy = _negocier(script, None, tmp_path)
    assert (tmp_path / "calibration.wav").is_file()
    assert policy.calibrated_s > 0
    # L'estimation du script existe, et elle diffère : preuve qu'on ne s'en sert pas.
    assert policy.calibrated_s != pytest.approx(script.estimated_total_s, abs=0.01)


@needs_espeak
def test_without_an_order_the_reference_rate_is_kept(script, tmp_path):
    policy = _negocier(script, None, tmp_path)
    assert policy.decision is DurationDecision.NO_TARGET
    assert policy.chosen_rate_wpm == policy.calibration_rate_wpm


# --------------------------------------------------------------- les décisions


@needs_espeak
def test_an_order_already_met_changes_nothing(script, tmp_path):
    """Si le débit de référence tombe juste, on n'y touche pas."""
    reference = _negocier(script, None, tmp_path).calibrated_s
    policy = _negocier(script, round(reference, 1), tmp_path)
    assert policy.decision is DurationDecision.ON_TARGET
    assert policy.chosen_rate_wpm == 165


@needs_espeak
def test_a_reachable_order_adjusts_the_rate(script, tmp_path):
    """Une cible atteignable dans la bande naturelle fait bouger le débit."""
    reference = _negocier(script, None, tmp_path).calibrated_s
    # +25 % : hors tolérance, mais largement dans la bande de débit.
    policy = _negocier(script, round(reference * 1.25, 1), tmp_path)
    assert policy.decision is DurationDecision.RATE_ADJUSTED
    assert policy.chosen_rate_wpm < 165
    assert NATURAL_RATE_MIN_WPM <= policy.chosen_rate_wpm <= NATURAL_RATE_MAX_WPM
    assert policy.within_tolerance


@needs_espeak
def test_an_order_beyond_the_content_is_declared_not_faked(script, tmp_path):
    """Le cas réel : 40 s pour un script qui n'en contient pas tant."""
    reference = _negocier(script, None, tmp_path).calibrated_s
    policy = _negocier(script, round(reference * 3, 1), tmp_path)
    assert policy.decision is DurationDecision.CONTENT_TOO_SHORT
    assert policy.chosen_rate_wpm == NATURAL_RATE_MIN_WPM
    assert "il manque du texte" in policy.rationale
    assert "seul le script le peut" in policy.rationale


@needs_espeak
def test_too_much_text_is_declared_too(script, tmp_path):
    reference = _negocier(script, None, tmp_path).calibrated_s
    policy = _negocier(script, round(reference / 3, 1), tmp_path)
    assert policy.decision is DurationDecision.CONTENT_TOO_LONG
    assert policy.chosen_rate_wpm == NATURAL_RATE_MAX_WPM


@needs_espeak
def test_the_rate_never_leaves_the_natural_band(script, tmp_path):
    reference = _negocier(script, None, tmp_path).calibrated_s
    for facteur in (0.2, 0.5, 1.0, 2.0, 5.0):
        policy = _negocier(script, round(reference * facteur, 1), tmp_path)
        assert NATURAL_RATE_MIN_WPM <= policy.chosen_rate_wpm <= NATURAL_RATE_MAX_WPM


@needs_espeak
def test_slowing_down_really_lengthens_the_audio(script, tmp_path):
    """Le levier employé produit bien l'effet annoncé, mesuré sur le WAV."""
    from pdz2.audio.wave_io import measure_wav

    texte = " ".join(line.text for line in script.lines)
    syn = EspeakSynthesiser()
    syn.synthesise(texte, VoiceSpec(voice_id="fr", rate_wpm=165), tmp_path / "a.wav")
    syn.synthesise(texte, VoiceSpec(voice_id="fr", rate_wpm=120), tmp_path / "b.wav")
    rapide = measure_wav(tmp_path / "a.wav").duration_s
    lent = measure_wav(tmp_path / "b.wav").duration_s
    assert lent > rapide * 1.2, f"{lent:.2f}s contre {rapide:.2f}s"


# ----------------------------------------------------------------- le contrat


def _policy(**changes) -> dict:
    base = dict(
        script_state_id="script_state-1",
        requested_s=40.0,
        calibrated_s=25.0,
        calibration_rate_wpm=165,
        chosen_rate_wpm=165,
        tolerance=0.15,
        decision=DurationDecision.ON_TARGET,
        rationale="essai",
        projected_s=25.0,
    )
    return base | changes


def test_on_target_with_a_changed_rate_is_refused():
    with pytest.raises(ValidationError, match="c'est un ajustement"):
        DurationPolicy(**_policy(chosen_rate_wpm=120))


def test_rate_adjusted_that_misses_the_target_is_refused():
    """Une décision ne peut pas prétendre atteindre ce qu'elle n'atteint pas."""
    with pytest.raises(ValidationError, match="la cible n'est pas atteinte"):
        DurationPolicy(
            **_policy(
                decision=DurationDecision.RATE_ADJUSTED,
                chosen_rate_wpm=120,
                projected_s=30.0,
            )
        )


def test_a_decision_without_an_order_is_refused():
    with pytest.raises(ValidationError, match="sans durée commandée"):
        DurationPolicy(**_policy(requested_s=None))


def test_no_target_with_an_order_is_refused():
    with pytest.raises(ValidationError, match="NO_TARGET avec une durée"):
        DurationPolicy(**_policy(decision=DurationDecision.NO_TARGET))


def test_the_policy_carries_no_estimate():
    """L'estimation du script n'entre dans aucune décision de durée."""
    assert "estimated" not in " ".join(DurationPolicy.model_fields)


# ------------------------------------------- l'opérateur reste souverain


class TestAnExplicitRateWins:
    """Un `--rate` passé en argument ne doit jamais être écrasé en silence.

    En branchant la négociation, j'ai d'abord fait exactement cela : le débit
    demandé par l'opérateur était remplacé par celui que la cible de durée
    imposait. Le test VOICE FIRST l'a attrapé — deux réglages moteur donnaient
    la même timeline, ce qui aurait vidé l'invariant de son sens.
    """

    def _episode(self, tmp_path):
        from pdz2.tests.test_cli_phase2 import _directed

        root = tmp_path / "ep"
        root.mkdir()
        return _directed(root)

    @needs_espeak
    def test_an_imposed_rate_survives_the_negotiation(self, tmp_path, capsys):
        from pdz2.cli.main import main
        from pdz2.contracts.script import DurationPolicy, VoiceTimeline

        episode, store = self._episode(tmp_path)
        main(["script", "--episode", str(episode)])
        assert main(["voice", "--episode", str(episode), "--rate", "200"]) == 0
        sortie = capsys.readouterr().out

        policy = store.load_as(DurationPolicy)
        timeline_avant = None
        if store.exists("voice_timeline"):
            timeline_avant = store.load_as(VoiceTimeline)
        # La négociation a bien eu lieu et reste consignée…
        assert policy.calibration_rate_wpm == 200
        # …mais le débit imposé n'a pas été remplacé.
        assert "débit imposé à 200" in sortie or policy.chosen_rate_wpm == 200
        assert timeline_avant is None or timeline_avant.total_duration_s > 0

    @needs_espeak
    def test_without_an_imposed_rate_the_negotiation_applies(self, tmp_path):
        from pdz2.cli.main import main
        from pdz2.contracts.script import DurationPolicy

        episode, store = self._episode(tmp_path)
        main(["script", "--episode", str(episode)])
        assert main(["voice", "--episode", str(episode)]) == 0
        policy = store.load_as(DurationPolicy)
        assert policy.calibration_rate_wpm == 165
        assert policy.decision is not None
