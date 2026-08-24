"""Reprise après interruption.

Le cas que la machine ne savait pas défaire : un processus tué **pendant** une
étape. Ctrl-C, mémoire épuisée, conteneur repris — l'étape reste `RUNNING` sur
le disque, et à la reprise `start()` la refuse pour toujours. L'épisode était
bloqué sans qu'aucun outil ne puisse le débloquer.

Ces tests fixent la différence entre les trois façons de défaire un état, que
rien ne doit confondre :

    recover()   une interruption   → l'étape redevient démarrable, gratuitement
    rewind()    une réparation     → l'étape et tout son aval, un cycle consommé
    abandon()   un renoncement     → l'épisode est clos
"""

from __future__ import annotations

import pytest

from pdz2.contracts.pipeline import EpisodeStatus, Stage, StageStatus
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore


def _interrompu(**kwargs) -> EpisodeStateMachine:
    """Un épisode dont le processus est mort au milieu de la recherche."""
    machine = EpisodeStateMachine.create(
        episode_id="ep", topic_request_id="topic_request-1", **kwargs
    )
    machine.start(Stage.RESEARCH)
    # Le processus meurt ici. Tout ce qui subsiste est l'instantané.
    return EpisodeStateMachine.resume(machine.snapshot)


# ------------------------------------------------------------ le blocage


def test_an_interrupted_stage_blocks_a_restart_without_recovery():
    """Le défaut d'origine : sans reprise, l'épisode est bloqué pour de bon."""
    repris = _interrompu()
    assert repris.snapshot.state(Stage.RESEARCH).status is StageStatus.RUNNING
    with pytest.raises(TransitionRefused, match="tourne déjà"):
        repris.start(Stage.RESEARCH, reason="rejeu")


def test_interrupted_stages_are_named():
    assert _interrompu().interrupted_stages == [Stage.RESEARCH]


def test_a_clean_episode_has_nothing_to_recover():
    machine = EpisodeStateMachine.create(
        episode_id="ep", topic_request_id="topic_request-1"
    )
    machine.start(Stage.RESEARCH)
    machine.complete(Stage.RESEARCH)
    assert machine.interrupted_stages == []
    assert machine.recover() == []


# ------------------------------------------------------------- la reprise


def test_recovery_makes_the_stage_startable_again():
    repris = _interrompu()
    assert repris.recover() == [Stage.RESEARCH]
    assert repris.snapshot.state(Stage.RESEARCH).status is StageStatus.PENDING
    repris.start(Stage.RESEARCH, reason="rejeu")  # ne lève plus


def test_recovery_costs_no_repair_cycle():
    """Une interruption n'est pas une réparation : elle ne doit rien coûter.

    C'est la raison d'être de `recover()`. `rewind()` aurait fonctionné
    mécaniquement, mais en consommant un cycle du budget de réparation —
    quelques plantages auraient épuisé la marge dont un vrai échec a besoin.
    """
    repris = _interrompu(max_repair_cycles=2)
    repris.recover()
    repris.recover()
    repris.recover()
    assert repris.snapshot.repair_cycles == 0


def test_recovery_leaves_the_downstream_alone():
    """L'aval n'a jamais démarré : il n'y a rien à y défaire."""
    repris = _interrompu()
    avant = {
        stage: repris.snapshot.state(stage).status
        for stage in Stage
        if stage is not Stage.RESEARCH
    }
    repris.recover()
    apres = {
        stage: repris.snapshot.state(stage).status
        for stage in Stage
        if stage is not Stage.RESEARCH
    }
    assert avant == apres


def test_recovery_forgets_the_artifacts_of_the_interrupted_stage():
    """On ne sait pas si un artefact commencé est complet : il ne compte pas."""
    machine = EpisodeStateMachine.create(
        episode_id="ep", topic_request_id="topic_request-1"
    )
    machine.start(Stage.RESEARCH)
    machine.snapshot.state(Stage.RESEARCH).artifact_ids = ["research_state-partiel"]
    repris = EpisodeStateMachine.resume(machine.snapshot)
    repris.recover()
    assert repris.snapshot.state(Stage.RESEARCH).artifact_ids == []


def test_the_interruption_stays_in_the_journal():
    """Une reprise silencieuse effacerait la trace de ce qui s'est passé."""
    repris = _interrompu()
    repris.recover(reason="conteneur repris")
    derniere = repris.snapshot.transitions[-1]
    assert derniere.from_status is StageStatus.RUNNING
    assert derniere.to_status is StageStatus.PENDING
    assert derniere.reason == "conteneur repris"


def test_a_recovery_without_a_reason_is_refused():
    with pytest.raises(TransitionRefused, match="motif"):
        _interrompu().recover(reason="   ")


def test_recovery_unblocks_a_failed_episode():
    repris = _interrompu()
    repris.snapshot.episode_status = EpisodeStatus.BLOCKED
    repris.recover()
    assert repris.snapshot.episode_status is EpisodeStatus.RUNNING


# ---------------------------------------------------- reprise depuis le disque


def test_a_recovered_episode_survives_a_round_trip_through_the_disk(tmp_path):
    """Le cas réel : un nouveau processus qui ne connaît que le dossier."""
    store = EpisodeStore(tmp_path / "ep")
    store.initialise()
    store.save_snapshot(_interrompu().snapshot)

    from pdz2.cli.main import main

    assert main(["state", "recover", str(tmp_path / "ep")]) == 0

    relu = EpisodeStateMachine.resume(EpisodeStore(tmp_path / "ep").load_snapshot())
    assert relu.interrupted_stages == []
    assert Stage.RESEARCH in relu.ready_stages()


def test_recovering_a_clean_episode_says_so(tmp_path, capsys):
    from pdz2.cli.main import main

    store = EpisodeStore(tmp_path / "ep")
    store.initialise()
    store.save_snapshot(
        EpisodeStateMachine.create(
            episode_id="ep", topic_request_id="topic_request-1"
        ).snapshot
    )
    assert main(["state", "recover", str(tmp_path / "ep")]) == 0
    assert "rien à reprendre" in capsys.readouterr().out
