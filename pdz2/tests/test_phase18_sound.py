"""Conception sonore : décidée, placée, et déclarée muette faute de source.

`ShotSpec.audio_events` était produit par la grammaire de plans — impact sur
la chute, souffle sur une opposition, ambiance quand le mouvement le porte —
validé par le contrat, puis jeté. Aucune piste n'en portait la trace.

Ces tests fixent l'aboutissement honnête : les repères existent, ils sont
placés sur la timeline de l'épisode, et l'absence de bibliothèque sonore est
**déclarée** plutôt que de faire disparaître la décision.

Rien ici ne synthétise de son. Un bruit fabriqué à la volée serait un son, pas
une conception sonore.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from pdz2.audio.library import (
    NO_SOUND_LIBRARIES,
    SoundLibrary,
    no_library_capability,
)
from pdz2.contracts.capability import CapabilityState, ProviderCapability
from pdz2.contracts.enums import AudioEventKind
from pdz2.contracts.sound import AudioCue, AudioDesign, CueState
from pdz2.engines.sound import SoundCompiler
from pdz2.tests import pipeline


@pytest.fixture(scope="module")
def episode(tmp_path_factory):
    return pipeline.build_episode(tmp_path_factory.mktemp("phase18"))


def _compile(episode, libraries=NO_SOUND_LIBRARIES):
    return SoundCompiler(libraries=libraries).compile(
        episode_id="ep",
        shot_graph=episode.graph,
        temporal_plan=episode.temporal_plan,
    )


# ------------------------------------------------ les décisions aboutissent


def test_the_decided_events_really_reach_the_design(episode):
    """Ce que la grammaire a décidé se retrouve, un pour un."""
    decides = [
        (shot.shot_id, event.kind)
        for shot in episode.graph.shots
        for event in shot.audio_events
    ]
    assert decides, "la fixture ne produirait rien à vérifier"
    design = _compile(episode).design
    places = [(cue.shot_id, cue.kind) for cue in design.cues]
    assert sorted(places) == sorted(decides)


def test_a_shot_instant_becomes_an_episode_instant(episode):
    """Le repère est placé au bon endroit de la timeline entière."""
    creneaux = {slot.shot_id: slot for slot in episode.temporal_plan.slots}
    for cue in _compile(episode).design.cues:
        creneau = creneaux[cue.shot_id]
        assert creneau.start_s <= cue.timeline_at_s <= creneau.end_s + 0.05


def test_no_cue_spills_past_the_end_of_the_episode(episode):
    design = _compile(episode).design
    for cue in design.cues:
        assert cue.timeline_at_s + cue.duration_s <= design.total_duration_s + 0.05


# --------------------------------------------- l'absence de son est déclarée


def test_without_a_library_every_cue_is_declared_unresolved(episode):
    design = _compile(episode).design
    assert design.silent
    assert not design.resolved
    assert len(design.unresolved) == len(design.cues)
    for cue in design.unresolved:
        assert "aucune bibliothèque sonore branchée" in cue.detail


def test_the_notes_say_the_episode_will_have_no_sound_design(episode):
    notes = " ".join(_compile(episode).notes)
    assert "sans habillage sonore" in notes


def test_the_repository_declares_no_sound_library():
    assert NO_SOUND_LIBRARIES == ()
    capability = no_library_capability()
    assert capability.state is CapabilityState.UNAVAILABLE
    assert capability.detail.strip()


# ------------------------------------------- la chaîne accepte une vraie source


class _Catalogue:
    """Bibliothèque de test : elle rend un fichier qui existe réellement."""

    name = "catalogue-de-test"

    def __init__(self, fichier: Path) -> None:
        self.fichier = fichier

    def get_capabilities(self) -> ProviderCapability:
        return ProviderCapability(
            provider=self.name,
            state=CapabilityState.AVAILABLE,
            measured_at=datetime.now(UTC),
            measurement_method="double de test",
            requires_network=False,
        )

    def resolve(self, kind: AudioEventKind, duration_s: float) -> Path | None:
        return self.fichier if kind is AudioEventKind.IMPACT else None


def test_the_port_is_satisfiable(tmp_path):
    fichier = tmp_path / "impact.wav"
    fichier.write_bytes(b"RIFF")
    assert isinstance(_Catalogue(fichier), SoundLibrary)


def test_a_real_library_resolves_what_it_covers(episode, tmp_path):
    """Le jour où un catalogue arrive, la chaîne le prend sans rien changer."""
    fichier = tmp_path / "impact.wav"
    fichier.write_bytes(b"RIFF")
    design = _compile(episode, libraries=(_Catalogue(fichier),)).design

    impacts = [c for c in design.cues if c.kind is AudioEventKind.IMPACT]
    if impacts:
        assert all(c.state is CueState.RESOLVED for c in impacts)
        assert all(c.source_path == str(fichier) for c in impacts)
        assert not design.silent
    autres = [c for c in design.cues if c.kind is not AudioEventKind.IMPACT]
    assert all(c.state is CueState.UNRESOLVED for c in autres)
    assert all("ne propose ce son" in c.detail for c in autres)


def test_an_unreachable_library_is_not_consulted(episode, tmp_path):
    class _Injoignable(_Catalogue):
        def get_capabilities(self):
            return ProviderCapability(
                provider=self.name,
                state=CapabilityState.UNAVAILABLE,
                measured_at=datetime.now(UTC),
                measurement_method="double de test",
                detail="catalogue hors ligne",
            )

    fichier = tmp_path / "impact.wav"
    fichier.write_bytes(b"RIFF")
    assert _compile(episode, libraries=(_Injoignable(fichier),)).design.silent


# ------------------------------------------------------------------ contrat


def _cue(**changes):
    base = dict(
        shot_id="S00",
        kind=AudioEventKind.IMPACT,
        timeline_at_s=1.0,
        duration_s=0.5,
        state=CueState.UNRESOLVED,
        detail="aucune source",
    )
    return AudioCue(**(base | changes))


def test_a_resolved_cue_without_a_source_is_refused():
    with pytest.raises(ValidationError, match="déclaré résolu sans source"):
        _cue(state=CueState.RESOLVED, detail="")


def test_an_unresolved_cue_with_a_source_is_refused():
    with pytest.raises(ValidationError, match="source renseignée"):
        _cue(source_path="/tmp/x.wav")


def test_a_silent_cue_must_say_why():
    with pytest.raises(ValidationError, match="sans raison"):
        _cue(detail="   ")


def test_a_cue_beyond_the_episode_is_refused():
    with pytest.raises(ValidationError, match="hors de l'épisode"):
        AudioDesign(
            episode_id="ep",
            shot_graph_id="shot_graph-1",
            total_duration_s=2.0,
            cues=[_cue(timeline_at_s=1.9, duration_s=1.0)],
        )
