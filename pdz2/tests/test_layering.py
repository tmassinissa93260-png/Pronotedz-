"""Tests d'architecture.

Ces tests ne vérifient pas un comportement mais une frontière. Ils échouent
le jour où quelqu'un mélange les trois couches, ou fait entrer un nom de
fournisseur dans le cœur du système.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pdz2.contracts import DirectorState, RenderSpecExecutable, RenderSpecRequested, registry

PACKAGE_ROOT = Path(__file__).resolve().parents[1]

EXECUTION_ONLY_PACKAGES = {
    "pdz2.providers",
    "pdz2.renderers",
    "pdz2.engines",
    "pdz2.qa",
    "pdz2.repair",
    "pdz2.audio",
    "pdz2.editing",
    "pdz2.cli",
    "pdz2.storage",
    "pdz2.state",
}

# Marques et noms commerciaux qui n'ont rien à faire dans le cœur : ils
# n'apparaissent, plus tard, que dans les adaptateurs et la matrice de
# capacités mesurées.
PROVIDER_BRANDS = (
    "openai",
    "anthropic",
    "runway",
    "pika",
    "luma",
    "kling",
    "veo",
    "sora",
    "elevenlabs",
    "groq",
    "replicate",
    "fal.ai",
    "falai",
    "stability",
    "midjourney",
    "comfyui",
)


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _python_files(package: str) -> list[Path]:
    directory = PACKAGE_ROOT / package
    return sorted(p for p in directory.rglob("*.py"))


class TestContractsStayIndependent:
    def test_contracts_import_nothing_from_the_execution_layers(self) -> None:
        offenders: list[str] = []
        for path in _python_files("contracts"):
            for module in _imports_of(path):
                for forbidden in EXECUTION_ONLY_PACKAGES:
                    if module == forbidden or module.startswith(f"{forbidden}."):
                        offenders.append(f"{path.name} importe {module}")
        assert not offenders, offenders

    def test_the_state_machine_only_knows_contracts(self) -> None:
        allowed_prefixes = ("pdz2.contracts", "pdz2.state")
        offenders: list[str] = []
        for path in _python_files("state"):
            for module in _imports_of(path):
                if module.startswith("pdz2.") and not module.startswith(allowed_prefixes):
                    offenders.append(f"{path.name} importe {module}")
        assert not offenders, offenders

    @pytest.mark.parametrize("package", ["contracts", "state", "storage", "schemas"])
    def test_no_provider_brand_in_the_core(self, package: str) -> None:
        offenders: list[str] = []
        for path in _python_files(package):
            lowered = path.read_text(encoding="utf-8").lower()
            for brand in PROVIDER_BRANDS:
                if brand in lowered:
                    offenders.append(f"{path.name} mentionne {brand!r}")
        assert not offenders, offenders


class TestLayerPurity:
    """NARRATIVE INTENT, RENDER SPECIFICATION et EXECUTION ne se mélangent pas."""

    RENDER_WORDS = {
        "provider",
        "model",
        "strategy",
        "fps",
        "resolution",
        "seed",
        "cost",
        "endpoint",
        "api",
    }

    def test_director_state_carries_no_render_field(self) -> None:
        leaked = [
            name
            for name in DirectorState.model_fields
            if any(word in name for word in self.RENDER_WORDS)
        ]
        assert not leaked, f"fuite d'exécution dans DirectorState : {leaked}"

    def test_shot_intent_carries_no_render_field(self) -> None:
        from pdz2.contracts import ShotIntent

        leaked = [
            name
            for name in ShotIntent.model_fields
            if any(word in name for word in self.RENDER_WORDS)
        ]
        assert not leaked, f"fuite d'exécution dans ShotIntent : {leaked}"

    def test_requested_spec_names_no_provider(self) -> None:
        fields = set(RenderSpecRequested.model_fields)
        assert "provider" not in fields
        assert "model" not in fields

    def test_executable_spec_is_the_only_side_that_names_a_provider(self) -> None:
        assert "provider" in RenderSpecExecutable.model_fields
        assert "model" in RenderSpecExecutable.model_fields

    def test_executable_spec_carries_no_narrative_field(self) -> None:
        narrative = {"thesis", "claim_id", "narrative_function", "audience", "tone"}
        leaked = narrative & set(RenderSpecExecutable.model_fields)
        assert not leaked, f"fuite narrative dans RenderSpecExecutable : {leaked}"


class TestNoArbitraryDictionaries:
    """Aucun dictionnaire libre ne remplace un contrat central."""

    def test_no_contract_exposes_a_raw_dict_field(self) -> None:
        offenders: list[str] = []
        for contract_type in registry.types():
            for name, field in contract_type.model_fields.items():
                annotation = str(field.annotation)
                if "dict[" in annotation.lower() or annotation.startswith("<class 'dict'"):
                    offenders.append(f"{contract_type.CONTRACT_NAME}.{name}: {annotation}")
        assert not offenders, offenders

    def test_every_contract_forbids_unknown_fields(self) -> None:
        offenders = [
            contract_type.CONTRACT_NAME
            for contract_type in registry.types()
            if contract_type.model_config.get("extra") != "forbid"
        ]
        assert not offenders, offenders


class TestPhaseHonesty:
    """Les paquets des phases suivantes restent vides, sans faux moteur."""

    @pytest.mark.parametrize(
        "package",
        ["providers", "renderers", "engines", "qa", "repair", "audio", "editing"],
    )
    def test_unimplemented_packages_contain_only_their_notice(self, package: str) -> None:
        files = _python_files(package)
        assert [p.name for p in files] == ["__init__.py"], (
            f"{package} contient du code alors que sa phase n'est pas faite"
        )
        text = files[0].read_text(encoding="utf-8")
        assert "non implémenté" in text
