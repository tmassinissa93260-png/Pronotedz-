"""Moteur de recherche : corpus, extraction, confiance, graphe, bout en bout."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts.research import (
    CausalRelation,
    ClaimKind,
    EvidenceStance,
    TopicRequest,
    VerificationStatus,
)
from pdz2.engines.research import (
    CapabilityState,
    ConfidenceModel,
    CorpusFormatError,
    EdgeRules,
    EvidenceSignal,
    ExtractionSettings,
    LocalCorpusProvider,
    NoUsableProvider,
    ProviderCapability,
    ResearchEngine,
    SearchQuery,
    demonstrability,
)
from pdz2.engines.research.corpus import parse_document
from pdz2.engines.research.extraction import (
    ClaimSignal,
    extract_candidates,
    group_duplicates,
)
from pdz2.engines.research.graph import GraphNode, build_edges
from pdz2.tests.fixtures import CORPUS

TOPIC = "Comment fonctionne une voiture électrique ?"


def request(**overrides) -> TopicRequest:
    payload = {"topic": TOPIC, "target_duration_s": 45.0}
    return TopicRequest(**(payload | overrides))


# ---------------------------------------------------------------- capacités


class TestCapabilityDeclaration:
    def test_an_unknown_capability_cannot_be_dated(self) -> None:
        with pytest.raises(ValidationError, match="UNKNOWN mais horodatée"):
            ProviderCapability(
                provider="x",
                state=CapabilityState.UNKNOWN,
                measured_at=__import__("datetime").datetime.now(
                    __import__("datetime").UTC
                ),
            )

    def test_a_measured_capability_needs_a_method(self) -> None:
        with pytest.raises(ValidationError, match="sans méthode"):
            ProviderCapability.measured("x", reachable=True, method="  ")

    def test_an_unavailable_capability_names_its_reason(self) -> None:
        with pytest.raises(ValidationError, match="sans raison"):
            ProviderCapability.measured("x", reachable=False, method="probe", detail="")

    def test_unknown_is_the_default_for_the_unmeasured(self) -> None:
        capability = ProviderCapability.unknown("x")
        assert capability.state is CapabilityState.UNKNOWN
        assert not capability.usable


class TestLocalCorpus:
    def test_a_real_corpus_is_reachable(self) -> None:
        capability = LocalCorpusProvider(CORPUS).get_capabilities()
        assert capability.usable
        assert capability.requires_network is False
        assert capability.measured_at is not None

    def test_a_missing_directory_is_reported_not_guessed(self, tmp_path) -> None:
        capability = LocalCorpusProvider(tmp_path / "absent").get_capabilities()
        assert capability.state is CapabilityState.UNAVAILABLE
        assert "introuvable" in capability.detail

    def test_an_empty_directory_is_unavailable(self, tmp_path) -> None:
        capability = LocalCorpusProvider(tmp_path).get_capabilities()
        assert capability.state is CapabilityState.UNAVAILABLE
        assert "vide" in capability.detail

    def test_search_ranks_by_relevance_and_is_stable(self) -> None:
        provider = LocalCorpusProvider(CORPUS)
        query = SearchQuery(text=TOPIC)
        first = [document.title for document in provider.search(query)]
        second = [document.title for document in provider.search(query)]
        assert first == second
        assert len(first) == 3

    def test_search_on_a_missing_corpus_raises(self, tmp_path) -> None:
        with pytest.raises(Exception, match="introuvable"):
            LocalCorpusProvider(tmp_path / "absent").search(SearchQuery(text=TOPIC))

    def test_a_document_without_a_header_is_refused(self, tmp_path) -> None:
        path = tmp_path / "nu.md"
        path.write_text("Le moteur tourne.", encoding="utf-8")
        with pytest.raises(CorpusFormatError, match="en-tête"):
            parse_document(path)

    def test_a_document_without_authority_is_refused(self, tmp_path) -> None:
        path = tmp_path / "sans.md"
        path.write_text("---\ntitle: X\n---\nTexte.", encoding="utf-8")
        with pytest.raises(CorpusFormatError, match="authority"):
            parse_document(path)

    def test_an_unknown_source_kind_is_refused(self, tmp_path) -> None:
        path = tmp_path / "bizarre.md"
        path.write_text(
            "---\ntitle: X\nauthority: 0.5\nkind: rumeur\n---\nTexte.", encoding="utf-8"
        )
        with pytest.raises(CorpusFormatError, match="type de source inconnu"):
            parse_document(path)

    def test_authority_outside_the_range_is_refused(self, tmp_path) -> None:
        path = tmp_path / "trop.md"
        path.write_text("---\ntitle: X\nauthority: 1.7\n---\nTexte.", encoding="utf-8")
        with pytest.raises(CorpusFormatError, match="hors de"):
            parse_document(path)


# --------------------------------------------------------------- extraction


class TestExtraction:
    def _candidates(self, text: str, **kwargs):
        return extract_candidates(topic=TOPIC, documents=[(0, text)], **kwargs)

    def test_a_causal_sentence_is_retained_as_a_mechanism(self) -> None:
        found = self._candidates(
            "Le moteur électrique convertit l'énergie de la batterie en rotation."
        )
        assert found and found[0].kind is ClaimKind.MECHANISM
        assert ClaimSignal.CAUSAL_CUE in found[0].signals

    def test_a_quantified_sentence_is_retained_as_a_quantity(self) -> None:
        found = self._candidates(
            "Le rendement d'une chaîne électrique de voiture atteint 90 % à la roue."
        )
        assert found and found[0].kind is ClaimKind.QUANTITY

    def test_a_question_is_never_a_claim(self) -> None:
        assert not self._candidates(
            "Comment le moteur électrique d'une voiture convertit-il l'énergie ?"
        )

    def test_a_sentence_too_short_is_ignored(self) -> None:
        assert not self._candidates("Le moteur tourne.")

    def test_a_sentence_without_any_signal_is_ignored(self) -> None:
        assert not self._candidates(
            "Les vacances au bord de la mer sont agréables au mois de juillet."
        )

    def test_extraction_is_deterministic(self) -> None:
        text = (CORPUS / "moteur.md").read_text(encoding="utf-8")
        first = [c.text for c in self._candidates(text)]
        second = [c.text for c in self._candidates(text)]
        assert first == second

    def test_max_per_document_is_honoured(self) -> None:
        text = (CORPUS / "moteur.md").read_text(encoding="utf-8")
        found = self._candidates(text, settings=ExtractionSettings(max_per_document=2))
        assert len(found) == 2


class TestDuplicateGrouping:
    def test_reformulations_of_one_claim_land_in_one_group(self) -> None:
        candidates = extract_candidates(
            topic=TOPIC,
            documents=[
                (0, "Le moteur électrique convertit l'énergie électrique de la "
                    "batterie en énergie mécanique de rotation."),
                (1, "Le moteur électrique convertit l'énergie électrique de la "
                    "batterie en mouvement de rotation de l'arbre."),
            ],
        )
        groups = group_duplicates(candidates, ExtractionSettings().duplicate_threshold)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_a_negated_variant_joins_the_group_it_contradicts(self) -> None:
        candidates = extract_candidates(
            topic=TOPIC,
            documents=[
                (0, "Le rendement d'une chaîne de traction électrique atteint 90 % "
                    "de l'énergie stockée restituée à la roue."),
                (1, "Le rendement d'une chaîne de traction électrique n'atteint pas "
                    "90 % de l'énergie restituée à la roue en conditions réelles."),
            ],
        )
        groups = group_duplicates(candidates, ExtractionSettings().duplicate_threshold)
        assert len(groups) == 1
        polarities = {candidate.negated for candidate in groups[0]}
        assert polarities == {True, False}

    def test_distinct_claims_stay_apart(self) -> None:
        candidates = extract_candidates(
            topic=TOPIC,
            documents=[
                (0, "Le stator d'un moteur de voiture, parcouru par un courant "
                    "alternatif, génère un champ magnétique tournant."),
                (1, "Une batterie de traction de voiture électrique stocke 60 kWh "
                    "d'énergie utilisable."),
            ],
        )
        groups = group_duplicates(candidates, ExtractionSettings().duplicate_threshold)
        assert len(groups) == 2


# --------------------------------------------------------------- confiance


class TestConfidenceModel:
    model = ConfidenceModel()

    def test_no_evidence_means_no_confidence(self) -> None:
        outcome = self.model.evaluate([])
        assert outcome.confidence == 0.0
        assert outcome.verification is VerificationStatus.UNVERIFIED

    def test_a_single_source_never_concludes(self) -> None:
        outcome = self.model.evaluate(
            [EvidenceSignal("a", EvidenceStance.SUPPORTS, 0.95, 0.95)]
        )
        assert outcome.verification is VerificationStatus.UNVERIFIED
        assert outcome.confidence <= 0.5

    def test_two_independent_sources_corroborate(self) -> None:
        outcome = self.model.evaluate(
            [
                EvidenceSignal("a", EvidenceStance.SUPPORTS, 0.9, 0.8),
                EvidenceSignal("b", EvidenceStance.SUPPORTS, 0.8, 0.9),
            ]
        )
        assert outcome.verification is VerificationStatus.CORROBORATED
        assert outcome.confidence > 0.5

    def test_two_quotes_from_one_source_do_not_corroborate(self) -> None:
        outcome = self.model.evaluate(
            [
                EvidenceSignal("a", EvidenceStance.SUPPORTS, 0.9, 0.8),
                EvidenceSignal("a", EvidenceStance.SUPPORTS, 0.9, 0.8),
            ]
        )
        assert outcome.supporting_sources == 1
        assert outcome.verification is VerificationStatus.UNVERIFIED

    def test_a_comparable_counter_source_disputes(self) -> None:
        outcome = self.model.evaluate(
            [
                EvidenceSignal("a", EvidenceStance.SUPPORTS, 0.9, 0.8),
                EvidenceSignal("b", EvidenceStance.CONTRADICTS, 0.8, 0.9),
            ]
        )
        assert outcome.verification is VerificationStatus.DISPUTED

    def test_only_counter_evidence_refutes_and_zeroes(self) -> None:
        outcome = self.model.evaluate(
            [EvidenceSignal("a", EvidenceStance.CONTRADICTS, 0.9, 0.9)]
        )
        assert outcome.verification is VerificationStatus.REFUTED
        assert outcome.confidence == 0.0

    def test_corroboration_bonus_has_diminishing_returns(self) -> None:
        def score(count: int) -> float:
            return self.model.evaluate(
                [
                    EvidenceSignal(f"s{index}", EvidenceStance.SUPPORTS, 0.8, 0.8)
                    for index in range(count)
                ]
            ).confidence

        gain_second = score(2) - score(1)
        gain_fourth = score(4) - score(3)
        assert gain_second > gain_fourth >= 0

    def test_the_explanation_shows_the_arithmetic(self) -> None:
        outcome = self.model.evaluate(
            [EvidenceSignal("a", EvidenceStance.SUPPORTS, 0.9, 0.8)]
        )
        assert "base" in outcome.explanation and "corroboration" in outcome.explanation


# ------------------------------------------------------------------- graphe


class TestGraphRules:
    def _node(self, index: int, text: str, kind: ClaimKind, doc: int = 0) -> GraphNode:
        return GraphNode(
            claim_id=f"claim-{index}",
            text=text,
            kind=kind,
            document_index=doc,
            sentence_index=index,
        )

    def test_adjacent_consequence_follows_its_mechanism(self) -> None:
        edges = build_edges(
            [
                self._node(0, "Le stator génère un champ magnétique tournant.",
                           ClaimKind.MECHANISM),
                self._node(1, "Le rotor s'aligne sur ce champ, donc l'arbre tourne.",
                           ClaimKind.CONSEQUENCE),
            ]
        )
        assert len(edges) == 1
        assert edges[0].relation is CausalRelation.CAUSES
        assert edges[0].explanation

    def test_a_quantity_quantifies_a_mechanism_it_overlaps(self) -> None:
        edges = build_edges(
            [
                self._node(0, "Le moteur électrique convertit l'énergie électrique "
                              "de la batterie en énergie mécanique de rotation.",
                           ClaimKind.MECHANISM),
                self._node(1, "Le rendement d'une chaîne de traction électrique "
                              "atteint 90 % de l'énergie restituée à la roue.",
                           ClaimKind.QUANTITY),
            ]
        )
        assert any(edge.relation is CausalRelation.QUANTIFIES for edge in edges)

    def test_a_cross_document_link_needs_a_stronger_overlap(self) -> None:
        """Deux documents peuvent partager du vocabulaire sans parler du même."""
        nodes = [
            self._node(0, "Le moteur électrique convertit l'énergie électrique de la "
                          "batterie en énergie mécanique de rotation.",
                       ClaimKind.MECHANISM, doc=0),
            self._node(1, "Le rendement d'un moteur thermique de série ne dépasse pas "
                          "40 % de l'énergie du carburant.",
                       ClaimKind.QUANTITY, doc=1),
        ]
        assert build_edges(nodes) == []

    def test_no_edge_creates_a_cycle(self) -> None:
        nodes = [
            self._node(index, f"Le champ magnétique tournant du stator entraîne le "
                              f"rotor, donc l'arbre tourne, étape {index}.",
                       ClaimKind.CONSEQUENCE)
            for index in range(4)
        ]
        edges = build_edges(nodes)
        successors: dict[str, list[str]] = {node.claim_id: [] for node in nodes}
        for edge in edges:
            successors[edge.from_claim_id].append(edge.to_claim_id)
        assert not _has_cycle(successors)

    def test_out_degree_is_capped(self) -> None:
        definition = self._node(
            0, "Une voiture électrique est un véhicule électrique à moteur électrique.",
            ClaimKind.DEFINITION,
        )
        users = [
            self._node(index, f"Le moteur électrique du véhicule électrique agit à "
                              f"l'étape {index} de la chaîne électrique.",
                       ClaimKind.MECHANISM)
            for index in range(1, 8)
        ]
        edges = build_edges([definition, *users], EdgeRules(max_out_degree=2))
        outgoing = [e for e in edges if e.from_claim_id == definition.claim_id]
        assert len(outgoing) <= 2


def _has_cycle(successors: dict[str, list[str]]) -> bool:
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        mark = state.get(node, 0)
        if mark == 1:
            return True
        if mark == 2:
            return False
        state[node] = 1
        for child in successors.get(node, ()):
            if visit(child):
                return True
        state[node] = 2
        return False

    return any(visit(node) for node in successors)


# ------------------------------------------------------- démontrabilité


class TestDemonstrability:
    def test_a_physical_mechanism_scores_high(self) -> None:
        score = demonstrability(
            "Le rotor tourne sous l'effet du champ magnétique du stator.",
            ClaimKind.MECHANISM,
        )
        assert score > 0.6

    def test_an_abstract_claim_scores_low(self) -> None:
        score = demonstrability(
            "Cette notion relève d'une théorie économique et politique.",
            ClaimKind.FACT,
        )
        assert score < 0.2

    def test_the_score_stays_within_bounds(self) -> None:
        for text, kind in (
            ("", ClaimKind.FACT),
            ("Le rotor tourne, le courant circule, la batterie chauffe à 60 °C.",
             ClaimKind.MECHANISM),
        ):
            assert 0.0 <= demonstrability(text, kind) <= 1.0


# ------------------------------------------------------------ bout en bout


class TestEngineEndToEnd:
    def _run(self, **overrides):
        engine = ResearchEngine(providers=[LocalCorpusProvider(CORPUS)], **overrides)
        return engine.run(request())

    def test_it_produces_a_closed_research_state(self) -> None:
        outcome = self._run()
        state = outcome.state
        assert state.sources and state.evidence and state.claims
        # Le contrat revalide l'intégrité référentielle à la construction ;
        # on vérifie ici que le moteur la respecte réellement.
        source_ids = {source.id for source in state.sources}
        evidence_ids = {item.id for item in state.evidence}
        assert all(item.source_id in source_ids for item in state.evidence)
        assert all(
            reference in evidence_ids
            for claim in state.claims
            for reference in claim.evidence_ids
        )

    def test_it_finds_a_corroborated_claim(self) -> None:
        claims = self._run().state.claims
        corroborated = [
            claim
            for claim in claims
            if claim.verification is VerificationStatus.CORROBORATED
        ]
        assert corroborated, "deux sources énoncent la conversion, elle doit corroborer"
        assert all(len(claim.evidence_ids) >= 2 for claim in corroborated)

    def test_it_finds_the_contradiction_between_two_sources(self) -> None:
        claims = self._run().state.claims
        disputed = [
            claim for claim in claims if claim.verification is VerificationStatus.DISPUTED
        ]
        assert disputed, "le corpus contient un rendement affirmé puis nié"
        assert "rendement" in disputed[0].text.lower()

    def test_no_claim_is_certain_without_evidence(self) -> None:
        for claim in self._run().state.claims:
            if not claim.evidence_ids:
                assert claim.confidence == 0.0

    def test_the_fact_graph_is_populated_and_ordered(self) -> None:
        graph = self._run().state.fact_graph
        assert graph.edges
        order = graph.topological_order()
        position = {claim: index for index, claim in enumerate(order)}
        for edge in graph.edges:
            assert position[edge.from_claim_id] < position[edge.to_claim_id]

    def test_open_questions_name_what_is_missing(self) -> None:
        state = self._run().state
        assert state.open_questions
        assert any("disputée" in question for question in state.open_questions)

    def test_the_run_is_reproducible(self) -> None:
        first, second = self._run().state, self._run().state
        assert [claim.text for claim in first.claims] == [
            claim.text for claim in second.claims
        ]
        assert [claim.confidence for claim in first.claims] == [
            claim.confidence for claim in second.claims
        ]

    def test_claims_are_cited_never_rewritten(self) -> None:
        """Une affirmation doit se retrouver mot pour mot dans une source."""
        state = self._run().state
        corpus_text = " ".join(
            path.read_text(encoding="utf-8") for path in sorted(CORPUS.glob("*.md"))
        )
        for claim in state.claims:
            assert claim.text in corpus_text, claim.text

    def test_it_measures_demonstrability_but_decides_nothing(self) -> None:
        state = self._run().state
        assert any(claim.demonstrability > 0.5 for claim in state.claims)
        # La décision appartient au Director Core : la recherche ne coche rien.
        assert all(not claim.visually_demonstrable for claim in state.claims)
        assert all(claim.visual_proof is None for claim in state.claims)

    def test_without_a_usable_provider_it_refuses_instead_of_returning_empty(
        self, tmp_path
    ) -> None:
        engine = ResearchEngine(providers=[LocalCorpusProvider(tmp_path / "absent")])
        with pytest.raises(NoUsableProvider, match="aucun fournisseur joignable"):
            engine.run(request())

    def test_with_no_provider_at_all_it_says_so(self) -> None:
        with pytest.raises(NoUsableProvider, match="aucun fournisseur déclaré"):
            ResearchEngine(providers=[]).run(request())

    def test_capabilities_are_reported_with_the_outcome(self) -> None:
        outcome = self._run()
        assert outcome.usable_providers == ["local_corpus"]
        assert outcome.capabilities[0].measured_at is not None
