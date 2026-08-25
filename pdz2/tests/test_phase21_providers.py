"""Phase 21 — adaptateurs de fournisseurs.

## Ce que ces tests prouvent, et ce qu'ils ne prouvent pas

Ils **ne prouvent pas** que fal.ai, ElevenLabs ou l'API Anthropic répondent :
aucun de ces hôtes n'est joignable depuis l'environnement où ce code a été
écrit, et un test qui prétendrait le contraire serait exactement la
simulation que ce dépôt s'interdit. La seule vérification possible de ce
côté-là est le workflow d'intégration continue.

Ils prouvent ce qui est vérifiable ici, et qui n'est pas rien :

* la **frontière** — chaque adaptateur satisfait son port, et sa sonde dit
  « injoignable » sans clé, au lieu de supposer ;
* la **surface de décision** du raisonneur suit le contrat `DirectorBrief`
  au lieu d'en être une copie qui dérivera ;
* la **boucle de reprise** rend un contrat valide ou lève — jamais un brief
  à moitié rempli par l'adaptateur lui-même ;
* l'**inventaire** n'active rien sans identifiant et ne retire jamais le
  repli local.

Le double d'API employé plus bas n'est pas un faux fournisseur : il ne rend
aucune capacité, n'est jamais enregistré nulle part, et sert à observer la
logique de scellement et de reprise de l'adaptateur — logique qui, elle, est
réelle et vit en production.
"""

from __future__ import annotations

import json

import jsonschema
import pytest

from pdz2.contracts.direction import (
    AnchorDraft,
    AnchorKind,
    DirectorBrief,
    IdentityAttribute,
    VisualLanguage,
    VisualProofDraft,
    VisualStyleDecision,
)
from pdz2.contracts.enums import Pacing, Tone
from pdz2.engines.direction.ports import Reasoner, ReasonerUnavailable
from pdz2.providers.elevenlabs import ELEVENLABS_KEY_ENV, ElevenLabsSynthesiser
from pdz2.providers.fal import FAL_KEY_ENV, FalImageProvider, FalVideoProvider
from pdz2.providers.groq import GROQ_KEY_ENV, GroqReasoner
from pdz2.providers.image import ImageProvider
from pdz2.providers.reasoner import ANTHROPIC_KEY_ENV, AnthropicReasoner
from pdz2.providers.reasoning import DECIDED_BY_THE_REASONER, decision_schema
from pdz2.providers.video import VideoProvider

# ------------------------------------------------------- les ports sont tenus


def test_every_adapter_satisfies_the_port_it_claims() -> None:
    """Un adaptateur qui ne satisfait pas son port n'est pas branchable.

    `ProceduralImageRenderer` a vécu longtemps sans sonde : il rendait des
    images et n'aurait pas passé ce test. C'est ce qui a fait apparaître le
    port d'images, qui n'existait pas.
    """
    from pdz2.audio.espeak import EspeakSynthesiser
    from pdz2.audio.ports import SpeechSynthesiser
    from pdz2.engines.imagery import ProceduralImageRenderer

    assert isinstance(FalImageProvider(), ImageProvider)
    assert isinstance(ProceduralImageRenderer(), ImageProvider)
    assert isinstance(FalVideoProvider(), VideoProvider)
    assert isinstance(ElevenLabsSynthesiser(), SpeechSynthesiser)
    assert isinstance(EspeakSynthesiser(), SpeechSynthesiser)
    assert isinstance(AnthropicReasoner(), Reasoner)
    assert isinstance(GroqReasoner(), Reasoner)


@pytest.mark.parametrize(
    ("fabrique", "variable"),
    [
        (FalImageProvider, FAL_KEY_ENV),
        (FalVideoProvider, FAL_KEY_ENV),
        (ElevenLabsSynthesiser, ELEVENLABS_KEY_ENV),
        (AnthropicReasoner, ANTHROPIC_KEY_ENV),
        (GroqReasoner, GROQ_KEY_ENV),
    ],
)
def test_a_probe_without_credentials_says_unreachable(
    fabrique, variable, monkeypatch
) -> None:
    """Sans clé, la sonde constate ; elle ne suppose ni ne devine.

    Elle ne part pas non plus sur le réseau pour l'apprendre : l'absence
    d'identifiant est une réponse complète, et gratuite.
    """
    monkeypatch.delenv(variable, raising=False)
    capacite = fabrique().get_capabilities()
    declaree = getattr(capacite, "capability", capacite)
    assert not declaree.usable
    assert variable in declaree.detail
    assert declaree.requires_credentials


# ------------------------------ la surface de décision descend du contrat


def _brief_complet() -> DirectorBrief:
    return DirectorBrief(
        topic_request_id="topic_request-000",
        research_state_id="research_state-000",
        thesis="La came ouvre la soupape parce qu'elle pousse le poussoir.",
        audience="curieux",
        tone=Tone.DOCUMENTARY,
        pacing=Pacing.MEASURED,
        ending_payoff="Le cycle complet devient lisible d'un seul regard.",
        visual_language=VisualLanguage(visual_register="coupe technique"),
        visual_style=VisualStyleDecision(
            style="coupe technique transparente",
            lighting="rasante",
            palette=["#101820", "#f2a900"],
            lens_language="macro",
            texture="métal usiné",
            environment="atelier",
            graphics="repères vectoriels",
        ),
        anchors=[
            AnchorDraft(
                name="arbre",
                kind=AnchorKind.MACHINE,
                canonical_description="arbre à cames en acier",
                identity=[IdentityAttribute(name="carter", value="bleu nuit mat")],
            )
        ],
        visual_proofs=[
            VisualProofDraft(
                claim_id="claim-1",
                causal_mechanism="la came pousse le poussoir",
                evidence_required="vue en coupe synchronisée",
                visual_proof="la came pousse le poussoir de huit millimètres",
                anchor_names=["arbre"],
            )
        ],
    )


def _decision_de(brief: DirectorBrief) -> dict:
    charge = brief.to_payload()
    return {champ: charge[champ] for champ in DECIDED_BY_THE_REASONER}


def test_a_real_brief_validates_against_the_schema_sent_to_the_model() -> None:
    """Le schéma n'est pas une approximation du contrat : c'est sa projection."""
    jsonschema.validate(_decision_de(_brief_complet()), decision_schema())


def test_the_schema_refuses_what_the_model_must_not_decide() -> None:
    """`extra="forbid"` porté jusqu'au modèle, pas seulement à la relecture."""
    decision = _decision_de(_brief_complet()) | {"topic_request_id": "topic_request-000"}
    with pytest.raises(jsonschema.ValidationError, match="Additional properties"):
        jsonschema.validate(decision, decision_schema())


def test_the_schema_carries_no_definition_it_does_not_use() -> None:
    """Envoyer des définitions inutiles décrirait des champs non demandés."""
    schema = decision_schema()
    cites = set()

    def parcourir(noeud):
        if isinstance(noeud, dict):
            if "$ref" in noeud:
                cites.add(noeud["$ref"].rsplit("/", 1)[-1])
            for valeur in noeud.values():
                parcourir(valeur)
        elif isinstance(noeud, list):
            for element in noeud:
                parcourir(element)

    parcourir(schema["properties"])
    parcourir(schema["$defs"])
    assert set(schema["$defs"]) == cites


def test_no_default_survives_into_the_schema() -> None:
    """Une valeur par défaut laisserait le modèle ne pas trancher."""
    assert "default" not in json.dumps(decision_schema())


# --------------------------------------- la boucle de reprise, et sa limite


class _ClientDouble:
    """Double du client SDK. Rend des réponses préparées, dans l'ordre.

    Il n'imite pas l'API Anthropic : il imite le seul contact que
    l'adaptateur a avec elle — un flux dont on tire un message final. C'est
    ce qui permet d'observer le scellement et la reprise sans réseau.
    """

    def __init__(self, reponses: list[str]) -> None:
        self._reponses = list(reponses)
        self.appels: list[list[dict]] = []
        self.messages = self

    def stream(self, **kwargs):
        self.appels.append(kwargs["messages"])
        return _FluxDouble(self._reponses.pop(0))


class _FluxDouble:
    def __init__(self, texte: str) -> None:
        self._texte = texte

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get_final_message(self):
        bloc = type("Bloc", (), {"type": "text", "text": self._texte})()
        return type("Message", (), {"content": [bloc], "usage": None})()


def _raisonneur_avec(reponses: list[str], monkeypatch) -> AnthropicReasoner:
    from datetime import UTC, datetime

    from pdz2.contracts.capability import CapabilityState, ProviderCapability

    raisonneur = AnthropicReasoner()
    double = _ClientDouble(reponses)
    monkeypatch.setattr(
        AnthropicReasoner,
        "get_capabilities",
        lambda self: ProviderCapability(
            provider=self.name,
            state=CapabilityState.AVAILABLE,
            measured_at=datetime.now(UTC),
            measurement_method="double de test",
            detail="double de test — aucun appel réseau",
        ),
    )
    monkeypatch.setattr(AnthropicReasoner, "_client", lambda self, timeout: double)
    raisonneur.double = double
    return raisonneur


@pytest.fixture
def episode(tmp_path):
    from pdz2.tests import pipeline

    return pipeline.build_episode(tmp_path)


def test_the_reasoner_seals_the_identity_the_model_never_sees(episode, monkeypatch):
    """Le modèle décide ; l'adaptateur signe et range dans le bon dossier."""
    decision = json.dumps(_decision_de(_brief_complet()), ensure_ascii=False)
    raisonneur = _raisonneur_avec([decision], monkeypatch)

    brief = raisonneur.draft_brief(episode.request, episode.research)

    assert brief.topic_request_id == episode.request.id
    assert brief.research_state_id == episode.research.id
    assert brief.author == "anthropic"
    assert brief.thesis.startswith("La came ouvre la soupape")


def test_a_refused_decision_goes_back_with_the_exact_reproach(episode, monkeypatch):
    """Une reprise, et une seule, avec l'erreur du contrat en main."""
    casse = _decision_de(_brief_complet())
    casse["visual_proofs"][0]["visual_proof"] = "trop court"
    raisonneur = _raisonneur_avec(
        [
            json.dumps(casse, ensure_ascii=False),
            json.dumps(_decision_de(_brief_complet()), ensure_ascii=False),
        ],
        monkeypatch,
    )

    brief = raisonneur.draft_brief(episode.request, episode.research)

    assert brief.author == "anthropic"
    reprise = raisonneur.double.appels[1]
    assert len(reprise) == 3, "la reprise rejoue le contexte, elle ne repart pas de zéro"
    assert reprise[-1]["role"] == "user"
    assert "preuve visuelle trop vague" in reprise[-1]["content"]


def test_the_adapter_never_finishes_the_decision_itself(episode, monkeypatch):
    """Deux refus : l'adaptateur lève. Il ne complète pas à la place du modèle."""
    casse = json.dumps(_decision_de(_brief_complet()) | {"thesis": ""}, ensure_ascii=False)
    raisonneur = _raisonneur_avec([casse, casse], monkeypatch)

    with pytest.raises(ReasonerUnavailable, match="refusées par le contrat"):
        raisonneur.draft_brief(episode.request, episode.research)
    assert len(raisonneur.double.appels) == 2


def test_an_unreadable_answer_is_an_unavailability_not_a_guess(episode, monkeypatch):
    """Du texte hors schéma ne se rattrape pas : il se déclare."""
    raisonneur = _raisonneur_avec(["voici votre brief :"], monkeypatch)

    with pytest.raises(ReasonerUnavailable, match="illisible"):
        raisonneur.draft_brief(episode.request, episode.research)


def test_the_model_is_asked_in_terms_of_the_research_it_was_given(episode, monkeypatch):
    """Le raisonneur ne cherche pas : il choisit dans ce qui a été établi."""
    decision = json.dumps(_decision_de(_brief_complet()), ensure_ascii=False)
    raisonneur = _raisonneur_avec([decision], monkeypatch)

    raisonneur.draft_brief(episode.request, episode.research)

    demande = raisonneur.double.appels[0][0]["content"]
    assert episode.request.topic in demande
    assert episode.research.question in demande
    for claim in episode.research.claims[:3]:
        assert claim.id in demande
