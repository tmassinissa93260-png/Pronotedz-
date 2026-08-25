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


def test_the_schema_points_nowhere_the_model_has_to_follow() -> None:
    """Aucun `$ref` : le modèle voit les champs là où il les écrit.

    Le premier appel qui a vraiment produit une décision est revenu avec des
    preuves visuelles réduites à un `claim_id` et un champ `description`
    inventé — signature d'un renvoi vers `$defs` que le modèle n'a pas suivi.
    Le service a refusé sa propre sortie contre le schéma, ce qui a rendu le
    diagnostic immédiat.
    """
    import json as _json

    schema = decision_schema()
    assert "$defs" not in schema
    assert "$ref" not in _json.dumps(schema)

    # Ce que le contrat exige d'une preuve visuelle est lisible sur place.
    preuve = schema["properties"]["visual_proofs"]["items"]
    assert set(preuve["required"]) == {
        "claim_id",
        "causal_mechanism",
        "evidence_required",
        "visual_proof",
        "anchor_names",
        "acknowledged_dispute",
    }
    assert preuve["additionalProperties"] is False
    # Et les énumérations aussi : pas de renvoi à suivre pour connaître le ton.
    assert "documentary" in schema["properties"]["tone"]["enum"]


def test_inlining_the_schema_costs_nothing() -> None:
    """Déplacer les définitions ne les duplique pas : chacune sert une fois.

    Si un contrat futur citait deux fois la même définition, l'inlining la
    copierait — et sur un plafond de huit mille jetons par minute, ça se
    verrait. Ce test le dirait avant le fournisseur.
    """
    import json as _json

    from pdz2.providers.groq import DEFAULT_TPM, _jetons

    assert _jetons(decision_schema()) < DEFAULT_TPM // 4, (
        "le schéma mange plus du quart du plafond par minute : "
        f"{_jetons(decision_schema())} jetons pour {DEFAULT_TPM} permis"
    )
    assert "$defs" not in _json.dumps(decision_schema())


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


# ------------------------------------------- le plafond par minute de Groq


def test_the_request_fits_under_the_free_tier_ceiling(episode) -> None:
    """La requête réelle tient sous 8 000 jetons/minute, avec de la réserve.

    Le premier appel réel a été refusé : 18 813 jetons demandés pour 8 000
    permis. La cause n'était pas le texte envoyé — 2 800 jetons — mais les
    16 000 réservés pour une sortie jamais écrite : Groq compte la réserve
    dans son plafond.
    """
    from pdz2.providers.groq import (
        _MARGE_JETONS,
        _TOOL_NAME,
        GroqReasoner,
        _accepte_aussi_une_chaine,
        _jetons,
    )
    from pdz2.providers.reasoning import SYSTEM, decision_schema, instruction

    raisonneur = GroqReasoner()
    outil = {
        "type": "function",
        "function": {
            "name": _TOOL_NAME,
            "description": "Rend la décision de réalisation demandée.",
            "parameters": _accepte_aussi_une_chaine(decision_schema()),
        },
    }
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": instruction(episode.request, episode.research)},
    ]
    entree = _jetons(messages) + _jetons(outil) + _MARGE_JETONS
    demande = entree + raisonneur._sortie_possible(entree)

    assert demande < raisonneur.tpm, f"{demande} demandés pour {raisonneur.tpm} permis"
    assert raisonneur.tpm - demande >= 300, "aucune réserve : un écart d'estimation refuse"


def test_a_ceiling_too_low_to_write_is_refused_not_truncated() -> None:
    """Mieux vaut dire non que rendre une décision coupée en deux."""
    from pdz2.providers.groq import GroqReasoner

    etroit = GroqReasoner(tpm=3000)
    with pytest.raises(ReasonerUnavailable, match="jetons pour écrire"):
        etroit._sortie_possible(2900)


def test_the_second_attempt_waits_for_the_window_instead_of_being_refused(
    monkeypatch,
) -> None:
    """La reprise arrive dans la même minute : on attend, on ne se cogne pas.

    Sans cela, la boucle de reprise du contrat produirait mécaniquement un
    refus de débit à chaque brief invalide — un échec provoqué par nous, pas
    par le modèle.
    """
    from pdz2.providers import groq as module

    dormi: list[float] = []
    monkeypatch.setattr(module.time, "sleep", dormi.append)

    raisonneur = module.GroqReasoner(tpm=8000)
    raisonneur._attendre_la_fenetre(7000)
    assert dormi == [], "le premier appel n'attend rien"

    raisonneur._attendre_la_fenetre(7000)
    assert len(dormi) == 1, "le second appel de la minute doit attendre"
    assert 0 < dormi[0] <= module._FENETRE_S
    assert any("attente" in note for note in raisonneur.notes)


def test_the_instruction_no_longer_repeats_the_schema_as_a_template(episode) -> None:
    """Le gabarit recopié disait deux fois ce que le schéma dit mieux.

    Mille jetons sur un plafond de huit mille, pour une redite : le schéma
    envoyé décrit la forme plus strictement qu'un exemple, et les
    affirmations que le gabarit rappelait sont dans le relevé de recherche.
    """
    from pdz2.providers.reasoning import instruction

    texte = instruction(episode.request, episode.research)
    assert "visual_proofs" not in texte, "le gabarit JSON est de retour"
    assert "_claim_text" not in texte
    # Ce qui compte, lui, est bien là.
    assert episode.request.topic in texte
    for claim in episode.research.claims[:3]:
        assert claim.id in texte


def test_a_shape_refused_by_the_service_is_retried_once(monkeypatch) -> None:
    """Le service refuse la sortie du modèle : on retente, une fois.

    Ce refus vient du modèle, pas de la requête — il a écrit quelque chose
    que le schéma n'accepte pas, et la même demande peut mieux tomber.
    Distinct de la reprise du contrat, qui explique au modèle ce qu'on lui
    reproche : ici il n'a rien produit d'exploitable à commenter.
    """
    import httpx

    from pdz2.providers import groq as module

    appels: list[int] = []
    valide = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {"function": {"arguments": '{"thesis": "une thèse"}'}}
                    ]
                }
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }

    def poste(url, **kwargs):
        appels.append(1)
        if len(appels) == 1:
            return httpx.Response(
                400,
                json={"error": {"message": "Tool call validation failed: …"}},
                request=httpx.Request("POST", url),
            )
        return httpx.Response(200, json=valide, request=httpx.Request("POST", url))

    monkeypatch.setattr(module.httpx, "post", poste)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setenv(module.GROQ_KEY_ENV, "clé-de-test")

    decision = module.GroqReasoner()._decide([{"role": "user", "content": "x"}])
    assert len(appels) == 2, "un refus de forme doit être retenté une fois"
    assert decision == {"thesis": "une thèse"}


def test_a_refused_key_is_never_retried(monkeypatch) -> None:
    """Retenter une clé refusée ne la rend pas valide : on s'arrête net."""
    import httpx

    from pdz2.providers import groq as module

    appels: list[int] = []

    def poste(url, **kwargs):
        appels.append(1)
        return httpx.Response(
            401,
            json={"error": {"message": "Invalid API Key"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(module.httpx, "post", poste)
    monkeypatch.setenv(module.GROQ_KEY_ENV, "clé-de-test")

    with pytest.raises(ReasonerUnavailable, match="clé refusée"):
        module.GroqReasoner()._decide([{"role": "user", "content": "x"}])
    assert len(appels) == 1


def test_groq_translates_the_boolean_dialect_without_loosening_the_contract(
    monkeypatch,
) -> None:
    """`"true"` rendu en chaîne redevient un booléen. Le contrat reste strict."""
    import httpx

    from pdz2.providers import groq as module

    rendu = {
        "visual_proofs": [
            {"claim_id": "c1", "acknowledged_dispute": "true"},
            {"claim_id": "c2", "acknowledged_dispute": "false"},
        ]
    }
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda url, **k: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {"function": {"arguments": json.dumps(rendu)}}
                            ]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        ),
    )
    monkeypatch.setenv(module.GROQ_KEY_ENV, "clé-de-test")

    decision = module.GroqReasoner()._decide([{"role": "user", "content": "x"}])
    aveux = [p["acknowledged_dispute"] for p in decision["visual_proofs"]]
    assert aveux == [True, False], f"dialecte non traduit : {aveux}"


# ------------------------------------ le repli tient à la synthèse, pas à la sonde


class _SondeVerteSyntheseMorte:
    """Un moteur qui se déclare joignable puis refuse de synthétiser.

    Ce n'est pas un cas de laboratoire : c'est exactement ce qu'a fait un
    service distant le 25/08/2026. Sa sonde répondait « 21 voix disponibles »,
    et la première synthèse rendait :

        402 — Free users cannot use library voices via the API.

    Sonde verte, production morte. Le registre promettait que le moteur local
    n'est jamais retiré d'une famille ; la promesse ne valait rien tant qu'elle
    n'était pas tenue au moment où elle sert.
    """

    name = "sonde-verte"
    default_voice_id = "peu-importe"

    def get_capabilities(self):
        from datetime import UTC, datetime

        from pdz2.contracts.capability import CapabilityState, ProviderCapability

        return ProviderCapability(
            provider=self.name,
            state=CapabilityState.AVAILABLE,
            measured_at=datetime.now(UTC),
            measurement_method="double de test",
            detail="se déclare joignable, et ment",
        )

    def synthesise(self, text, voice, out_path):
        from pdz2.audio.errors import SynthesisFailed

        raise SynthesisFailed("402 — palier gratuit : voix refusée")


def test_a_provider_that_dies_at_synthesis_falls_back_to_the_local_engine(
    tmp_path, monkeypatch, capsys
) -> None:
    """La production continue en local, et la dégradation est dite."""
    from pdz2.audio.espeak import EspeakSynthesiser
    from pdz2.cli import phase2
    from pdz2.providers.registry import ActiveProviders

    if not EspeakSynthesiser().get_capabilities().usable:
        pytest.skip("eSpeak NG absent")

    from pdz2.tests import pipeline

    episode = pipeline.build_episode(tmp_path)
    monkeypatch.setattr(
        phase2,
        "active_providers",
        lambda: ActiveProviders(
            video=(),
            image=(),
            speech=(_SondeVerteSyntheseMorte(), EspeakSynthesiser()),
            reasoners=(),
            sound_libraries=(),
            notes=(),
        ),
    )

    class _Args:
        rate, voice, pitch, gap = 165, None, 50, 0

    rendu = phase2._synthetiser_avec_repli(
        script=episode.script,
        request=episode.request,
        workdir=tmp_path / "audio",
        lines_dir=tmp_path / "lines",
        args=_Args(),
    )

    assert rendu.moteur.name == "espeak-ng", "le repli local n'a pas pris le relais"
    assert rendu.ecarts, "un repli silencieux est un journal faux"
    assert "sonde-verte" in rendu.ecarts[0]
    assert "402" in rendu.ecarts[0]
    # VOICE FIRST tient malgré le repli : les durées sortent de l'audio produit.
    assert all(ligne.duration_s > 0 for ligne in rendu.outcome.lines)


def test_every_engine_dying_is_a_refusal_not_a_silent_empty_episode(
    tmp_path, monkeypatch
) -> None:
    """Si personne ne parle, on refuse — on ne rend pas un épisode muet."""
    from pdz2.audio.errors import SynthesiserUnavailable
    from pdz2.cli import phase2
    from pdz2.providers.registry import ActiveProviders
    from pdz2.tests import pipeline

    episode = pipeline.build_episode(tmp_path)
    monkeypatch.setattr(
        phase2,
        "active_providers",
        lambda: ActiveProviders(
            video=(),
            image=(),
            speech=(_SondeVerteSyntheseMorte(), _SondeVerteSyntheseMorte()),
            reasoners=(),
            sound_libraries=(),
            notes=(),
        ),
    )

    class _Args:
        rate, voice, pitch, gap = 165, None, 50, 0

    with pytest.raises(SynthesiserUnavailable, match="aucun moteur de voix"):
        phase2._synthetiser_avec_repli(
            script=episode.script,
            request=episode.request,
            workdir=tmp_path / "audio",
            lines_dir=tmp_path / "lines",
            args=_Args(),
        )


def test_no_voice_identifier_is_invented_for_an_account(monkeypatch) -> None:
    """Choisir une voix de bibliothèque pour un compte gratuit était une supposition.

    Elle était fausse, et le service l'a dit : « Free users cannot use library
    voices via the API. » On lit le catalogue du compte, et à défaut on
    déclare l'indisponibilité — le moteur local prendra le relais.
    """
    from pdz2.audio.errors import SynthesiserUnavailable
    from pdz2.providers.elevenlabs import ELEVENLABS_VOICE_ENV, ElevenLabsSynthesiser

    monkeypatch.delenv(ELEVENLABS_VOICE_ENV, raising=False)
    nu = ElevenLabsSynthesiser()
    with pytest.raises(SynthesiserUnavailable, match="aucune voix utilisable"):
        assert nu.default_voice_id

    # Le catalogue du compte tranche, et ce qui lui appartient passe devant.
    garni = ElevenLabsSynthesiser()
    garni._catalogue = [
        {"voice_id": "commune", "category": "premade"},
        {"voice_id": "la-sienne", "category": "cloned"},
    ]
    assert garni.default_voice_id == "la-sienne"

    monkeypatch.setenv(ELEVENLABS_VOICE_ENV, "imposée")
    assert garni.default_voice_id == "imposée", "un choix explicite prime"


# --------------------------- ce qu'un contrat n'exige pas, un modèle l'ignore


def test_the_palette_rule_reaches_the_model_and_the_door() -> None:
    """La règle vivait dans une docstring : invisible des deux côtés.

    Un raisonneur a rendu « bleu électrique, gris acier, blanc pur ». Le brief
    a été accepté, enregistré, et la compilation visuelle est tombée trois
    étapes plus loin sur une trace d'exécution. Deux endroits l'ignoraient :
    le schéma envoyé au modèle, qui n'annonçait qu'une liste de chaînes, et le
    contrat du brief, qui ne vérifiait rien.
    """
    from pydantic import ValidationError as _ValidationError

    from pdz2.contracts.direction import VisualStyleDecision

    # Le modèle lit la contrainte avant d'écrire.
    palette = decision_schema()["properties"]["visual_style"]["properties"]["palette"]
    assert palette["items"]["pattern"] == "^#[0-9a-fA-F]{6}$"
    assert "hexadécimale" in palette["items"]["description"]

    # Et s'il l'ignore quand même, le refus est immédiat.
    with pytest.raises(_ValidationError):
        VisualStyleDecision(
            style="coupe technique",
            lighting="rasante",
            palette=["bleu électrique", "gris acier"],
            lens_language="macro",
            texture="métal",
            environment="atelier",
            graphics="repères",
        )


def test_one_hex_rule_governs_the_brief_and_the_bible() -> None:
    """La même règle des deux côtés de la frontière, définie une fois.

    Elle existait en double — une docstring dans le brief, un validateur dans
    la bible — et les deux ne disaient pas la même chose : l'un décrivait,
    l'autre refusait. C'est ainsi qu'une palette invalide traverse.
    """
    from pdz2.contracts.direction import VisualStyleDecision
    from pdz2.contracts.visual import ColorScheme

    def motif(modele, champ):
        return modele.model_json_schema()["properties"][champ]["items"]["pattern"]

    assert motif(VisualStyleDecision, "palette") == motif(ColorScheme, "palette")
